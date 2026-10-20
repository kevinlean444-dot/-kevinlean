"""Contrato JSON v1, sin GTK; contenido indexado y stat seguro de la nota seleccionada."""
from contextlib import closing
import json
import stat
from pathlib import Path
import sqlite3

from .core import manifest_digest
from .locking import RecoveryNeeded, SpaceBusy, space_lock

__all__ = ['search', 'inspect_document', 'status']


class ContractError(Exception):
    def __init__(self, code, message, action):
        super().__init__(message)
        self.code, self.action = code, action


def _envelope(operation, data=None, error=None):
    return dict(version=1, operation=operation, ok=error is None,
                state='ready' if error is None else error.code, data=data,
                error=None if error is None else dict(code=error.code, message=str(error), action=error.action))


def _respond(workspace, operation, callback):
    try:
        with space_lock(workspace, allow_recovery=False) as (_, state):
            if not (state / 'index.sqlite').is_file():
                raise ContractError('index_missing', 'No hay índice SQLite', 'index')
            if not (state / 'manifest.json').is_file():
                raise ContractError('manifest_missing', 'No hay manifiesto de identidad', 'restore_manifest')
            try:
                manifest = json.loads((state / 'manifest.json').read_text(encoding='utf-8'))
                if manifest.get('version') != 2 or not isinstance(manifest.get('documents'), dict) or not isinstance(manifest.get('bindings'), dict):
                    raise ValueError('Formato incompatible')
            except (ValueError, UnicodeError, AttributeError) as exc:
                raise ContractError('manifest_invalid', 'Manifiesto inválido o incompatible', 'restore_manifest') from exc
            with closing(sqlite3.connect(f"{(state / 'index.sqlite').as_uri()}?mode=ro", uri=True)) as db:
                db.row_factory = sqlite3.Row
                db.execute('BEGIN')
                if db.execute('PRAGMA user_version').fetchone()[0] != 4:
                    raise ContractError('index_stale', 'Índice antiguo: vuelve a indexar', 'index')
                fingerprint = db.execute("SELECT value FROM metadata WHERE key=?", ('manifest_digest',)).fetchone()
                if fingerprint is None or fingerprint[0] != manifest_digest(manifest):
                    raise ContractError('index_stale', 'SQLite no corresponde al manifiesto actual', 'index')
                return _envelope(operation, callback(db, manifest))
    except ContractError as exc:
        return _envelope(operation, error=exc)
    except SpaceBusy:
        error = ContractError('busy', 'Espacio ocupado por otra operación', 'retry')
    except RecoveryNeeded:
        error = ContractError('recovery_needed', 'Hay una publicación pendiente de recuperación', 'index')
    except FileNotFoundError:
        error = ContractError('index_missing', 'No hay metadatos de indexación', 'index')
    except sqlite3.Error:
        error = ContractError('index_invalid', 'No se pudo consultar el índice SQLite', 'index')
    except ValueError:
        error = ContractError('workspace_invalid', 'Ruta o metadatos del espacio inseguros', 'inspect_workspace')
    except OSError:
        error = ContractError('io_error', 'No se pudo leer el estado del espacio', 'inspect_workspace')
    return _envelope(operation, error=error)


def _brief(record, identity):
    return dict(uuid=identity, title=record.get('title') or Path(record['rel_path']).stem,
                rel_path=record['rel_path'])


def _conflicts(manifest, identity):
    record = manifest['documents'][identity]
    paths = {record['rel_path'], *record.get('previous_paths', [])}
    return sorted([c for c in manifest.get('conflicts', []) if c['id'] == identity or paths.intersection(c['candidates'])],
                  key=lambda c: (c['id'], c['old_path']))


def _document(db, manifest, identity):
    record = manifest['documents'][identity]
    indexed = db.execute('SELECT deleted FROM docs WHERE id=?', (identity,)).fetchone()
    backlinks = db.execute('SELECT count(DISTINCT source) FROM links WHERE target=?', (identity,)).fetchone()[0]
    updates = db.execute('SELECT count(*) FROM links WHERE (source=? OR target=?) AND needs_update=1', (identity, identity)).fetchone()[0]
    return dict(**_brief(record, identity), kind=record.get('kind', 'note'),
                content_hash=record.get('content_hash'), identity_origin='frontmatter' if record.get('explicit_id') else 'manifest',
                deleted=bool(record.get('deleted')), indexed=indexed is not None and not indexed['deleted'],
                backlink_count=backlinks, has_conflicts=bool(_conflicts(manifest, identity)), needs_update_count=updates)


def _link_rows(db, manifest, column, identity, limit, offset):
    # column is an internal constant, never caller-supplied SQL.
    sql = f'''SELECT l.*, l.rowid-1 AS position, p.line, p.context FROM links l
              JOIN link_locations p ON p.position=l.rowid-1 WHERE l.{column}=? ORDER BY l.rowid LIMIT ? OFFSET ?'''
    records = manifest['documents']
    rows = []
    for row in db.execute(sql, (identity, limit, offset)):
        rows.append(dict(position=row['position'], source=_brief(records[row['source']], row['source']),
                         target=None if row['target'] is None else _brief(records[row['target']], row['target']),
                         raw=row['raw'], status=row['status'], candidate_uuids=json.loads(row['candidates']),
                         needs_update=bool(row['needs_update']), line=row['line'], context=row['context']))
    return rows


def search(workspace, text, *, limit=20, offset=0):
    """Búsqueda literal por frase; rank ascendente, luego ruta y UUID."""
    def perform(db, manifest):
        if not isinstance(text, str) or len(text) > 500 or type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 10000:
            raise ContractError('invalid_request', 'Texto máximo 500 caracteres; limit 1..100 y offset 0..10000', 'fix_request')
        rows, total = [], 0
        if text.strip():
            phrase = '"' + text.replace('"', '""') + '"'
            total = db.execute('SELECT count(*) FROM search JOIN docs ON docs.id=search.id WHERE search MATCH ? AND docs.kind=?', (phrase, 'note')).fetchone()[0]
            matches = db.execute('''SELECT docs.id, snippet(search, 1, '[', ']', ' … ', 24) AS excerpt,
                                    bm25(search) AS relevance FROM search JOIN docs ON docs.id=search.id
                                    WHERE search MATCH ? AND docs.kind=? ORDER BY relevance, docs.path, docs.id LIMIT ? OFFSET ?''',
                                 (phrase, 'note', limit, offset)).fetchall()
            for row in matches:
                rows.append(dict(**_document(db, manifest, row['id']), snippet=row['excerpt'], relevance=row['relevance']))
        return dict(query=text, limit=limit, offset=offset, total=total,
                    next_offset=offset + len(rows) if offset + len(rows) < total else None, results=rows)
    return _respond(workspace, 'search', perform)


def _disk_state(workspace, record):
    root = Path(workspace).absolute()
    path = root / record['rel_path']
    try:
        if not path.is_relative_to(root) or any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root)) or not path.resolve().is_relative_to(root):
            return dict(state='unsafe', modified=None)
        info = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            return dict(state='unsafe', modified=None)
        if not info.st_mode & 0o444:
            return dict(state='unreadable', modified=None)
        changed = any(record.get(k) is not None and record[k] != value for k, value in
                      (('size', info.st_size), ('device', info.st_dev), ('inode', info.st_ino), ('mtime_ns', info.st_mtime_ns)))
        state = 'modified' if changed else 'current' if record.get('mtime_ns') is not None else 'unknown'
        return dict(state=state, modified=changed if state != 'unknown' else None)
    except FileNotFoundError:
        return dict(state='missing', modified=None)
    except OSError:
        return dict(state='unreadable', modified=None)


def _link_page(db, column, identity, limit, offset):
    total = db.execute(f'SELECT count(*) FROM links WHERE {column}=?', (identity,)).fetchone()[0]
    return dict(limit=limit, offset=offset, total=total,
                next_offset=offset + limit if offset + limit < total else None)


def inspect_document(workspace, document, *, link_limit=50, backlinks_offset=0, outgoing_offset=0):
    def perform(db, manifest):
        if not isinstance(document, str) or not document:
            raise ContractError('invalid_request', 'Indica UUID o ruta relativa', 'fix_request')
        if type(link_limit) is not int or not 1 <= link_limit <= 100 or any(type(n) is not int or not 0 <= n <= 1000000 for n in (backlinks_offset, outgoing_offset)):
            raise ContractError('invalid_request', 'link_limit 1..100; offsets 0..1000000', 'fix_request')
        pages = dict(backlinks=dict(limit=link_limit, offset=backlinks_offset, total=0, next_offset=None),
                     outgoing_links=dict(limit=link_limit, offset=outgoing_offset, total=0, next_offset=None))
        records = manifest['documents']
        if document in records:
            identity = document
        else:
            matches = [i for i, r in records.items() if r['rel_path'] == document and not r.get('deleted')]
            if not matches:
                matches = [i for i, r in records.items() if r['rel_path'] == document]
            if len(matches) > 1:
                raise ContractError('document_ambiguous', 'Varias identidades históricas usan esa ruta; indica UUID', 'choose_document')
            if not matches:
                errors = [dict(r) for r in db.execute('SELECT * FROM errors WHERE path=? ORDER BY error', (document,))]
                if errors:
                    return dict(document=None, backlinks=[], outgoing_links=[], link_pages=pages, disk_state=None, health=dict(errors=errors, conflicts=[], historical_reference_count=0))
                raise ContractError('not_found', 'Documento no registrado', 'choose_document')
            identity = matches[0]
        paths = {records[identity]['rel_path'], *records[identity].get('previous_paths', [])}
        errors = [dict(r) for r in db.execute('SELECT * FROM errors ORDER BY path,error') if r['path'] in paths]
        pages['backlinks'] = _link_page(db, 'target', identity, link_limit, backlinks_offset)
        pages['outgoing_links'] = _link_page(db, 'source', identity, link_limit, outgoing_offset)
        return dict(document=_document(db, manifest, identity), backlinks=_link_rows(db, manifest, 'target', identity, link_limit, backlinks_offset),
                    outgoing_links=_link_rows(db, manifest, 'source', identity, link_limit, outgoing_offset),
                    link_pages=pages, disk_state=_disk_state(workspace, records[identity]),
                    health=dict(errors=errors, conflicts=_conflicts(manifest, identity),
                                historical_reference_count=sum(v == identity for v in manifest['bindings'].values())))
    return _respond(workspace, 'inspect', perform)


def status(workspace):
    def perform(db, manifest):
        counts = dict(notes=db.execute("SELECT count(*) FROM docs WHERE deleted=0 AND kind='note'").fetchone()[0],
                      attachments=db.execute("SELECT count(*) FROM docs WHERE deleted=0 AND kind='attachment'").fetchone()[0],
                      links=db.execute('SELECT count(*) FROM links').fetchone()[0],
                      needs_update=db.execute('SELECT count(*) FROM links WHERE needs_update=1').fetchone()[0],
                      conflicts=len(manifest.get('conflicts', [])),
                      errors=db.execute('SELECT count(*) FROM errors').fetchone()[0],
                      orphans=sum(bool(r.get('deleted')) for r in manifest['documents'].values()))
        for key, state in (('broken', 'unresolved'), ('ambiguous', 'ambiguous'), ('external', 'external'), ('outside', 'outside'), ('invalid', 'invalid')):
            counts[key] = db.execute('SELECT count(*) FROM links WHERE status=?', (state,)).fetchone()[0]
        return dict(counts=counts, conflicts=sorted(manifest.get('conflicts', []), key=lambda c: (c['id'], c['old_path'])),
                    errors=[dict(r) for r in db.execute('SELECT * FROM errors ORDER BY path,error')])
    return _respond(workspace, 'status', perform)
