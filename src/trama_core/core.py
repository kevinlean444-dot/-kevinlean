"""Sin acceso a red ni ejecución de documentos; todas las rutas son locales."""
import copy
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from urllib.parse import unquote, urlsplit
import uuid

MAX_BYTES = 2 * 1024 * 1024
MAX_FILES = 10000
LINK = re.compile(r"\[\[([^\]\n]+)\]\]|!?\[[^\]\n]*\]\(([^)\n]+)\)")
SCHEMA = """
CREATE TABLE docs(id TEXT PRIMARY KEY, path TEXT, title TEXT, hash TEXT, kind TEXT, deleted INTEGER NOT NULL);
CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED, body, tokenize='unicode61 remove_diacritics 2');
CREATE TABLE links(source TEXT, raw TEXT, target TEXT, status TEXT, candidates TEXT, needs_update INTEGER NOT NULL);
CREATE TABLE errors(path TEXT, error TEXT);
CREATE TABLE conflicts(details TEXT NOT NULL);
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
    for name in ("manifest.json", "index.sqlite", "index.sqlite-journal", "manifest.tmp", "manifest.next.json", "index.next.sqlite", "index.next.sqlite-journal", "pending", "pending.tmp"):
        p = state / name
        if p.exists() or p.is_symlink():
            if p.is_symlink() or not p.is_file() or p.stat().st_nlink != 1:
                raise ValueError(f"Archivo de estado inseguro: {name}")
    recover(state)
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


def index(workspace, relocate=None, *, _manifest=None, _prepare=False):
    root, state = root_state(workspace, True)
    manifest_path = state / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"version": 2, "documents": {}, "bindings": {}}
    if _manifest is not None:
        manifest = copy.deepcopy(_manifest)
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
    observations = {}
    explicit_ids = set()
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
                if identity in seen:
                    raise ValueError("UUID duplicado: conflicto, archivo excluido")
                info = p.stat(follow_symlinks=False)
                observations[rel] = dict(size=len(data), device=info.st_dev, inode=info.st_ino)
                if explicit:
                    explicit_ids.add(identity)
                seen.add(identity)
                docs.append((identity, rel, title, hashlib.sha256(data).hexdigest(), kind))
                bodies[identity] = body
            except (OSError, ValueError) as exc:
                errors.append((rel, str(exc)))
    # Reconcile only after observing the entire space: copies cannot win by scan order.
    missing = {i: r for i, r in records.items() if i not in seen
               and not r.get("deleted") and not r.get("explicit_id")
               and not (root / r["rel_path"]).exists()}
    fresh = [d for d in docs if d[0] not in records and d[0] not in explicit_ids]
    transfers = {}
    conflicts = manifest.setdefault("conflicts", [])
    for old_id, record in sorted(missing.items()):
        candidates = [d for d in fresh if d[3] == record.get("content_hash")
                      and d[4] == record.get("kind")]
        peers = [i for i, r in missing.items() if r.get("content_hash") == record.get("content_hash")
                 and r.get("kind") == record.get("kind")]
        if len(candidates) > 1 or (candidates and len(peers) > 1):
            conflict = dict(id=old_id, old_path=record["rel_path"],
                            candidates=sorted(d[1] for d in candidates))
            if conflict not in conflicts:
                conflicts.append(conflict)
            errors.append((record["rel_path"], "Renombre ambiguo: " + ", ".join(conflict["candidates"])))
        elif len(candidates) == 1:
            doc = candidates[0]
            info = observations[doc[1]]
            if all(record.get(k) == info[k] for k in ("size", "device", "inode")):
                transfers[doc[0]] = old_id
            else:
                errors.append((record["rel_path"], "Renombre no confirmado; use --relocate UUID RUTA antes de indexar"))
    if relocate:
        old_id, new_path = relocate
        if old_id not in missing:
            raise ValueError("--relocate requiere UUID importado con ruta anterior desaparecida")
        choices = [d for d in fresh if d[1] == new_path]
        if len(choices) != 1:
            raise ValueError("--relocate requiere ruta nueva, legible y sin UUID ni registro previo")
        # Explicit evidence supplied by the user; never infer from a changed hash.
        transfers = {new: old for new, old in transfers.items() if old != old_id}
        transfers[choices[0][0]] = old_id
    for n, doc in enumerate(docs):
        old_id = transfers.get(doc[0])
        if old_id:
            bodies[old_id] = bodies.pop(doc[0])
            seen.remove(doc[0])
            seen.add(old_id)
            docs[n] = (old_id, *doc[1:])
    for identity, record in records.items():
        location = root / record["rel_path"]
        record["deleted"] = not location.resolve().is_relative_to(root) or not location.exists()
    for identity, rel, title, digest, kind in docs:
        prior = records.get(identity, {})
        previous_paths = list(prior.get("previous_paths", []))
        if prior.get("rel_path") and prior["rel_path"] != rel and prior["rel_path"] not in previous_paths:
            previous_paths.append(prior["rel_path"])
        records[identity] = dict(rel_path=rel, content_hash=digest, title=title, kind=kind,
                                 deleted=False, explicit_id=identity in explicit_ids,
                                 previous_paths=previous_paths, **observations[rel])
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
                    links.append((identity, raw, None, "invalid", "[]", 0))
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
            needs_update = status == "unresolved" and previous in seen
            if needs_update:
                candidates, status = [previous], "resolved"
            if status == "resolved":
                new_bindings[key] = candidates[0]
            elif status == "unresolved" and previous in records:
                new_bindings[key] = previous
            links.append((identity, raw, candidates[0] if len(candidates) == 1 else None, status, json.dumps(candidates), int(needs_update)))
    manifest["bindings"] = new_bindings
    prepared = dict(manifest=manifest, docs=docs, bodies=bodies, links=links, errors=errors, conflicts=conflicts)
    if _prepare:
        return prepared
    publish(state, prepared)
    return {"documents": len(docs), "links": len(links), "errors": [dict(path=p, error=e) for p, e in errors]}


def recover(state):
    """Finish an interrupted two-file publication before exposing state."""
    marker = state / "pending"
    if marker.exists():
        for staged, target in (("index.next.sqlite", "index.sqlite"), ("manifest.next.json", "manifest.json")):
            path = state / staged
            if path.exists():
                path.replace(state / target)
        sync_directory(state)
        marker.unlink()
        sync_directory(state)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(state, prepared):
    manifest, docs, bodies, links, errors, conflicts = (prepared[k] for k in
        ("manifest", "docs", "bodies", "links", "errors", "conflicts"))
    records = manifest["documents"]
    seen = {d[0] for d in docs}
    staged = state / "index.next.sqlite"
    staged.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(state / "index.next.sqlite")) as db, db:
            db.execute("BEGIN IMMEDIATE")
            for table in ("docs", "search", "links", "errors", "conflicts"):
                db.execute(f"DROP TABLE IF EXISTS {table}")
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    db.execute(statement)
            db.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?)", [(*d, 0) for d in docs])
            db.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?)", [
                (i, r["rel_path"], r.get("title", ""), r.get("content_hash"), r.get("kind", "note"), 1)
                for i, r in records.items() if r.get("deleted") and i not in seen])
            db.execute("PRAGMA user_version=3")
            db.executemany("INSERT INTO search VALUES (?,?)", bodies.items())
            db.executemany("INSERT INTO links VALUES (?,?,?,?,?,?)", links)
            db.executemany("INSERT INTO errors VALUES (?,?)", errors)
            db.executemany("INSERT INTO conflicts VALUES (?)", [(json.dumps(c, ensure_ascii=False),) for c in conflicts])
        next_manifest = state / "manifest.next.json"
        next_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        for path in (staged, next_manifest):
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        marker = state / "pending.tmp"
        marker.write_text("ready\n", encoding="ascii")
        with marker.open("rb") as stream:
            os.fsync(stream.fileno())
        sync_directory(state)
        marker.replace(state / "pending")
        sync_directory(state)
        recover(state)
    finally:
        # After intent publication leave staged files for recovery on the next command.
        if not (state / "pending").exists():
            for name in ("index.next.sqlite", "manifest.next.json", "pending.tmp"):
                (state / name).unlink(missing_ok=True)


def query(workspace, command, value=None):
    _, state = root_state(workspace)
    if not (state / "index.sqlite").is_file():
        raise ValueError("Primero ejecuta index")
    try:
        with closing(sqlite3.connect(f"{(state / 'index.sqlite').as_uri()}?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            if command == "search":
                # Literal phrase: user input never becomes FTS operators.
                phrase = '"' + value.replace('"', '""') + '"'
                return [dict(r) for r in db.execute("SELECT docs.* FROM search JOIN docs ON docs.id=search.id WHERE search MATCH ? ORDER BY path", (phrase,))]
            if command == "backlinks":
                return [dict(r) for r in db.execute("SELECT DISTINCT d.* FROM links l JOIN docs d ON d.id=l.source JOIN docs t ON t.id=l.target WHERE (t.id=? OR t.path=?) AND t.deleted=0 AND d.deleted=0 ORDER BY d.path", (value, value))]
            result = {"version": 3, "identity_conflicts": [json.loads(r[0]) for r in db.execute("SELECT details FROM conflicts ORDER BY details")]}
            for key, sql in (("documents", "SELECT * FROM docs WHERE deleted=0 ORDER BY path"), ("deleted_documents", "SELECT * FROM docs WHERE deleted=1 ORDER BY path,id"), ("links", "SELECT * FROM links ORDER BY source,raw"), ("errors", "SELECT * FROM errors ORDER BY path")):
                result[key] = [dict(r) for r in db.execute(sql)]
            for link in result["links"]:
                link["candidates"] = json.loads(link["candidates"])
            return result
    except sqlite3.Error as exc:
        raise RuntimeError(f"Error SQLite: {exc}") from exc
