"""Proyección paginada de problemas; las sugerencias nunca se aplican a documentos."""
import posixpath
import json
from collections import Counter
from urllib.parse import quote, urlsplit, urlunsplit

from .core import LINK

CATEGORIES = ('all', 'needs_update', 'broken', 'ambiguous', 'conflicts')


def _replacement(source, target, match, unique_title):
    relative = posixpath.relpath(target['rel_path'], posixpath.dirname(source['rel_path']) or '.')
    destination = quote(relative, safe='/')
    title = target['title']
    if match.group(1) is not None:
        if unique_title and title.strip() == title and title and not any(c in title for c in ']\n\r'):
            return dict(destination=title, replacement=f'[[{title}]]')
        return dict(destination=destination, replacement=f'[nota]({destination})')
    old = urlsplit(match.group(2))
    destination = urlunsplit(('', '', destination, old.query, old.fragment))
    # Conserva la etiqueta original y el indicador de imagen, reemplaza solo el destino.
    prefix = match.group(0)[:match.group(0).rfind('](') + 2]
    return dict(destination=destination, replacement=prefix + destination + ')')


def read_health(db, manifest, category, limit, offset):
    from .ui_contract import ContractError, _brief
    if category not in CATEGORIES or type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 1000000:
        raise ContractError('invalid_request', 'Filtro all/needs_update/broken/ambiguous/conflicts; limit 1..100; offset 0..1000000', 'fix_request')
    # El filtro es un parámetro; solo se materializa la página solicitada en Python.
    cte = '''WITH issues AS (
        SELECT CASE WHEN l.needs_update=1 THEN 'needs_update'
                    WHEN l.status='ambiguous' THEN 'ambiguous' ELSE 'broken' END AS category,
               l.rowid AS position, d.path AS path, NULL AS details
        FROM links l JOIN docs d ON d.id=l.source
        WHERE l.needs_update=1 OR l.status IN ('unresolved','ambiguous')
        UNION ALL
        SELECT 'conflicts', rowid, '', details FROM conflicts
    ) '''
    params = (category, category)
    predicate = "WHERE (?='all' OR category=?)"
    total = db.execute(cte + 'SELECT count(*) FROM issues ' + predicate, params).fetchone()[0]
    page = db.execute(cte + 'SELECT * FROM issues ' + predicate + ' ORDER BY category,path,details,position LIMIT ? OFFSET ?',
                      (*params, limit, offset)).fetchall()
    records = manifest['documents']
    title_counts = Counter(_brief(record, identity)['title'].casefold()
                           for identity, record in records.items() if not record.get('deleted'))
    rows = []
    # Caché de una sola fuente: nunca retiene todos los textos del espacio.
    cached_source, matches = None, None
    for issue in page:
        if issue['category'] == 'conflicts':
            conflict = json.loads(issue['details'])
            identity = conflict['id']
            candidates = sorted((_brief(r, i) for i, r in records.items()
                                 if not r.get('deleted') and r['rel_path'] in conflict['candidates']),
                                key=lambda r: (r['rel_path'], r['uuid']))
            rows.append(dict(key='conflict:' + identity + ':' + conflict['old_path'], category='conflicts',
                             source=_brief(records[identity], identity), line=None, context=None,
                             raw=None, current_link=None, suggestions=[], candidates=candidates, conflict=conflict))
            continue
        link = db.execute('''SELECT l.*, p.line,p.context,
                          (SELECT count(*) FROM links x WHERE x.source=l.source AND x.rowid<l.rowid) AS ordinal
                          FROM links l JOIN link_locations p ON p.position=l.rowid-1 WHERE l.rowid=?''',
                          (issue['position'],)).fetchone()
        source = _brief(records[link['source']], link['source'])
        if cached_source != (issue['category'], link['source']):
            cached_source = (issue['category'], link['source'])
            body = db.execute('SELECT body FROM search WHERE id=?', (link['source'],)).fetchone()[0]
            # Iterador, sin lista de coincidencias potencialmente enorme.
            matches = iter(enumerate(LINK.finditer(body)))
        # El orden por ruta y rowid garantiza ordinal creciente para cada fuente.
        match = next(m for n, m in matches if n == link['ordinal'])
        candidates = sorted((_brief(records[i], i) for i in json.loads(link['candidates'])),
                            key=lambda r: (r['rel_path'], r['uuid']))
        suggestions = []
        for target in candidates:
            count = title_counts[target['title'].casefold()]
            suggestions.append(dict(target=target, **_replacement(source, target, match, count == 1)))
        rows.append(dict(key='link:' + str(issue['position'] - 1), category=issue['category'], source=source,
                         line=link['line'], context=link['context'], raw=link['raw'],
                         current_link=match.group(0), suggestions=suggestions, candidates=candidates, conflict=None))
    return dict(category=category, limit=limit, offset=offset, total=total,
                next_offset=offset + len(rows) if offset + len(rows) < total else None, items=rows)
