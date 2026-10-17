"""Sin acceso a red ni ejecución de documentos; todas las rutas son locales."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
from urllib.parse import unquote, urlsplit
import uuid

MAX_BYTES = 2 * 1024 * 1024
MAX_FILES = 10000
LINK = re.compile(r"\[\[([^\]\n]+)\]\]|!?\[[^\]\n]*\]\(([^)\n]+)\)")
SCHEMA = """
CREATE TABLE docs(id TEXT PRIMARY KEY, path TEXT, title TEXT, hash TEXT, kind TEXT, deleted INTEGER NOT NULL);
CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED, body, tokenize='unicode61 remove_diacritics 2');
CREATE TABLE links(source TEXT, raw TEXT, target TEXT, status TEXT, candidates TEXT);
CREATE TABLE errors(path TEXT, error TEXT);
"""


def root_state(workspace, create=False):
    root = Path(workspace).absolute()
    if root.is_symlink() or not root.is_dir() or root.resolve() != root:
        raise ValueError("El espacio debe ser un directorio real sin symlinks en su ruta")
    state = root / ".trama"
    if state.is_symlink():
        raise ValueError(".trama no puede ser un symlink")
    if create:
        state.mkdir(exist_ok=True)
    for name in ("manifest.json", "index.sqlite", "index.sqlite-journal", "manifest.tmp"):
        p = state / name
        if p.exists() or p.is_symlink():
            if p.is_symlink() or not p.is_file() or p.stat().st_nlink != 1:
                raise ValueError(f"Archivo de estado inseguro: {name}")
    return root, state


def read_document(path):
    # O_NOFOLLOW blocks replacement of the final component with a symlink.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o444:
            raise ValueError("Archivo no regular o no legible")
        data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Supera el límite de 2 MiB")
    return data


def metadata(text, fallback):
    identity = None
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end < 0:
            raise ValueError("Front matter sin cierre")
        ids = re.findall(r"^id:\s*(.*?)\s*$", text[4:end], re.M)
        if len(ids) > 1:
            raise ValueError("Múltiples campos id")
        if ids:
            identity = str(uuid.UUID(ids[0].strip("\"'")))
            if uuid.UUID(identity).version != 4:
                raise ValueError("El id debe ser UUIDv4")
    heading = re.search(r"^#\s+(.+)$", text, re.M)
    return identity, heading.group(1).strip() if heading else fallback


def assign_identity(path, data, identity):
    """Opt-in; preserve bytes, permissions, and reject hardlinks/replacements."""
    newline = b"\r\n" if data.startswith(b"---\r\n") else b"\n"
    field = b"id: " + identity.encode("ascii") + newline
    if data.startswith(b"---" + newline):
        updated = b"---" + newline + field + data[3 + len(newline):]
    else:
        updated = b"---\n" + field + b"---\n" + data
    if len(updated) > MAX_BYTES:
        raise ValueError("UUID excedería el límite de tamaño")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("No se asigna ID a archivos no regulares o hardlinks")
        if stream.read(MAX_BYTES + 1) != data:
            raise ValueError("Archivo cambió durante indexación")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".trama-id-", dir=path.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode))
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        current = path.lstat()
        if (current.st_ino, current.st_dev, current.st_mtime_ns, current.st_size) != (info.st_ino, info.st_dev, info.st_mtime_ns, info.st_size):
            raise ValueError("Archivo cambió durante asignación")
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return updated


def index(workspace, assign_ids=False):
    root, state = root_state(workspace, True)
    manifest_path = state / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"version": 2, "documents": {}, "bindings": {}}
    if manifest.get("version") == 1 and isinstance(manifest.get("paths"), dict):
        migrated = {}
        for path, identity in manifest["paths"].items():
            if identity in migrated:
                raise ValueError("Manifiesto v1 ambiguo: UUID repetido; requiere revisión")
            migrated[identity] = {"rel_path": path, "content_hash": None, "deleted": False}
        manifest = {"version": 2, "documents": migrated, "bindings": {}}
    if manifest.get("version") != 2 or not isinstance(manifest.get("documents"), dict) or not isinstance(manifest.get("bindings"), dict):
        raise ValueError("Manifiesto incompatible")
    records = manifest["documents"]
    for identity, record in records.items():
        if str(uuid.UUID(identity)) != identity or not isinstance(record, dict):
            raise ValueError("Registro de identidad inválido")
        rel = record.get("rel_path")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError("Ruta insegura en manifiesto")
    identities = {r["rel_path"]: identity for identity, r in records.items() if not r.get("deleted")}
    bindings = manifest["bindings"]
    docs, bodies, errors, seen = [], {}, [], set()
    count = 0
    def walk_error(exc):
        errors.append((os.path.relpath(exc.filename, root), str(exc)))

    for base, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs.sort()
        for name in list(dirs):
            p = Path(base) / name
            if name.startswith(".") or p.is_symlink():
                dirs.remove(name)
                if p.is_symlink():
                    errors.append((p.relative_to(root).as_posix(), "Symlink omitido"))
        for name in sorted(files):
            if name.startswith("."):
                continue
            count += 1
            if count > MAX_FILES:
                raise ValueError("Espacio superior a 10000 archivos")
            p = Path(base) / name
            rel = p.relative_to(root).as_posix()
            try:
                data = read_document(p)
                kind = "note" if p.suffix.lower() in (".md", ".txt") else "attachment"
                body = data.decode("utf-8") if kind == "note" else ""
                explicit, title = metadata(body.replace("\r\n", "\n"), p.stem)
                identity = explicit or identities.get(rel) or str(uuid.uuid4())
                identity = str(uuid.UUID(identity))
                if assign_ids and p.suffix.lower() == ".md" and explicit is None:
                    if uuid.UUID(identity).version != 4:
                        raise ValueError("ID previo no es UUIDv4")
                    data = assign_identity(p, data, identity)
                    body = data.decode("utf-8")
                if identity in seen:
                    raise ValueError("UUID duplicado: conflicto, archivo excluido")
                seen.add(identity)
                docs.append((identity, rel, title, hashlib.sha256(data).hexdigest(), kind))
                bodies[identity] = body
            except (OSError, ValueError) as exc:
                errors.append((rel, str(exc)))
    for identity, record in records.items():
        location = root / record["rel_path"]
        record["deleted"] = not location.resolve().is_relative_to(root) or not location.exists()
    for identity, rel, title, digest, kind in docs:
        records[identity] = dict(rel_path=rel, content_hash=digest, title=title, kind=kind, deleted=False)
    by_path = {d[1]: d[0] for d in docs}
    titles = {}
    for identity, path, title, digest, kind in docs:
        titles.setdefault(title.casefold(), []).append(identity)
    links = []
    new_bindings = {}
    for identity, path, *_ in docs:
        for match in LINK.finditer(bodies[identity]):
            wiki, markdown = match.groups()
            raw = wiki if wiki is not None else markdown
            candidates = []
            if wiki is not None:
                candidates = titles.get(wiki.strip().casefold(), [])
                status = "resolved" if len(candidates) == 1 else "ambiguous" if candidates else "unresolved"
            else:
                try:
                    parsed = urlsplit(raw)
                except ValueError:
                    links.append((identity, raw, None, "invalid", "[]"))
                    continue
                if parsed.scheme or parsed.netloc:
                    status = "external"
                else:
                    dest = unquote(parsed.path)
                    candidate = (root / path).parent / dest if dest else root / path
                    lexical = Path(os.path.abspath(candidate))
                    blocked = not lexical.is_relative_to(root)
                    if not blocked:
                        blocked = any(p.is_symlink() for p in (lexical, *lexical.parents) if p.is_relative_to(root))
                    if dest.startswith("/") or blocked or not candidate.resolve().is_relative_to(root):
                        status = "outside"
                    else:
                        relative = candidate.resolve().relative_to(root).as_posix()
                        candidates = [by_path[relative]] if relative in by_path else []
                        status = "resolved" if candidates else "unresolved"
            key = json.dumps([identity, raw], ensure_ascii=False)
            previous = bindings.get(key)
            if status == "unresolved" and previous in seen:
                candidates, status = [previous], "resolved"
            if status == "resolved":
                new_bindings[key] = candidates[0]
            elif status == "unresolved" and previous in records:
                new_bindings[key] = previous
            links.append((identity, raw, candidates[0] if len(candidates) == 1 else None, status, json.dumps(candidates)))
    manifest["bindings"] = new_bindings
    # Save identity and bindings first; database is a rebuildable projection.
    temp = state / "manifest.tmp"
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(manifest_path)
    with sqlite3.connect(state / "index.sqlite") as db:
        db.execute("BEGIN IMMEDIATE")
        for table in ("docs", "search", "links", "errors"):
            db.execute(f"DROP TABLE IF EXISTS {table}")
        for statement in SCHEMA.split(";"):
            if statement.strip():
                db.execute(statement)
        db.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?)", [(*d, 0) for d in docs])
        db.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?)", [
            (i, r["rel_path"], r.get("title", ""), r.get("content_hash"), r.get("kind", "note"), 1)
            for i, r in records.items() if r.get("deleted") and i not in seen])
        db.execute("PRAGMA user_version=2")
        db.executemany("INSERT INTO search VALUES (?,?)", bodies.items())
        db.executemany("INSERT INTO links VALUES (?,?,?,?,?)", links)
        db.executemany("INSERT INTO errors VALUES (?,?)", errors)
    return {"documents": len(docs), "links": len(links), "errors": [dict(path=p, error=e) for p, e in errors]}


def query(workspace, command, value=None):
    _, state = root_state(workspace)
    if not (state / "index.sqlite").is_file():
        raise ValueError("Primero ejecuta index")
    try:
        with sqlite3.connect(f"{(state / 'index.sqlite').as_uri()}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            if command == "search":
                # Literal phrase: user input never becomes FTS operators.
                phrase = '"' + value.replace('"', '""') + '"'
                return [dict(r) for r in db.execute("SELECT docs.* FROM search JOIN docs ON docs.id=search.id WHERE search MATCH ? ORDER BY path", (phrase,))]
            if command == "backlinks":
                return [dict(r) for r in db.execute("SELECT DISTINCT d.* FROM links l JOIN docs d ON d.id=l.source JOIN docs t ON t.id=l.target WHERE (t.id=? OR t.path=?) AND t.deleted=0 AND d.deleted=0 ORDER BY d.path", (value, value))]
            result = {"version": 2}
            for key, sql in (("documents", "SELECT * FROM docs WHERE deleted=0 ORDER BY path"), ("deleted_documents", "SELECT * FROM docs WHERE deleted=1 ORDER BY path,id"), ("links", "SELECT * FROM links ORDER BY source,raw"), ("errors", "SELECT * FROM errors ORDER BY path")):
                result[key] = [dict(r) for r in db.execute(sql)]
            for link in result["links"]:
                link["candidates"] = json.loads(link["candidates"])
            return result
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error SQLite: {exc}") from exc
