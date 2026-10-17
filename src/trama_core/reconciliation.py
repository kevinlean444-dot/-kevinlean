"""Inspección y confirmación explícita; nunca abre documentos para escritura."""
import copy
import hashlib
import json
import os
from pathlib import Path

from .core import index, metadata, publish, query, read_document, root_state


def load(workspace):
    root, state = root_state(workspace)
    manifest = json.loads((state / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version') != 2:
        raise ValueError('Ejecuta index para migrar el manifiesto primero')
    # Validate persisted paths/identities using the same rules as index, without saving.
    observed = index(workspace, _manifest=manifest, _prepare=True)
    return root, state, manifest, observed


def safe_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts or any(p.startswith('.') for p in path.parts):
        raise ValueError('Ruta fuera del espacio o no indexable')
    path = root / path
    if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root)):
        raise ValueError('No se permiten symlinks')
    if not path.resolve().is_relative_to(root):
        raise ValueError('Ruta fuera del espacio')
    return path


def conflicts(workspace):
    root, _, manifest, _ = load(workspace)
    records = manifest['documents']
    graph = query(workspace, 'graph')
    rows = []
    for identity, record in sorted(records.items()):
        if not record.get('deleted') and not any(c['id'] == identity for c in manifest.get('conflicts', [])):
            continue
        pending = [c for c in manifest.get('conflicts', []) if c['id'] == identity]
        recorded_paths = {p for c in pending for p in c['candidates']}
        candidates = []
        for current, candidate in sorted(records.items(), key=lambda item: (item[1]['rel_path'], item[0])):
            if candidate.get('deleted') or candidate.get('explicit_id') or candidate.get('kind') != record.get('kind'):
                continue
            path = safe_path(root, candidate['rel_path'])
            if not path.is_file():
                continue
            candidates.append(dict(id=current, rel_path=candidate['rel_path'],
                                   content_hash=candidate['content_hash'],
                                   hash_match=candidate['content_hash'] == record.get('content_hash'),
                                   recorded_candidate=candidate['rel_path'] in recorded_paths))
        rows.append(dict(id=identity, old_path=record['rel_path'], content_hash=record.get('content_hash'),
                         pending_conflicts=pending, candidates=candidates,
                         historical_references=sum(v == identity for v in manifest['bindings'].values()),
                         indexed_backlinks=sum(e['target'] == identity for e in graph['links']),
                         old_path_exists=os.path.lexists(root / record['rel_path'])))
    return dict(orphans=rows)


def resolve(workspace, old_id, destination, apply=False):
    root, state, original, observed = load(workspace)
    records = original['documents']
    if old_id not in records:
        raise ValueError('UUID histórico desconocido')
    old = records[old_id]
    original_path = safe_path(root, old['rel_path'])
    if os.path.lexists(original_path):
        raise ValueError('Ambos archivos coexisten: la ruta original sigue presente')
    if not old.get('deleted'):
        raise ValueError('El UUID original no está marcado como histórico; ejecuta index')
    if destination in records:
        current_id = destination
    else:
        safe_path(root, destination)
        matches = [i for i, r in records.items() if r['rel_path'] == destination and not r.get('deleted')]
        if len(matches) != 1:
            raise ValueError('La ruta destino no existe en el índice activo; ejecuta index')
        current_id = matches[0]
    current = records[current_id]
    if current_id == old_id or current.get('deleted'):
        raise ValueError('El destino debe ser otro UUID activo')
    path = safe_path(root, current['rel_path'])
    if not path.is_file():
        raise ValueError('La ruta destino no existe')
    data = read_document(path)
    if current.get('kind') == 'note':
        explicit, _ = metadata(data.decode('utf-8').replace('\r\n', '\n'), path.stem)
        if explicit is not None:
            raise ValueError('El destino tiene UUID canónico en frontmatter; no se puede absorber')
    if current.get('explicit_id'):
        raise ValueError('El destino no es una identidad local temporal')
    if current.get('kind') != old.get('kind'):
        raise ValueError('Tipos de documento incompatibles')
    if hashlib.sha256(data).hexdigest() != current['content_hash']:
        raise ValueError('El destino cambió desde index; reindexa antes de resolver')
    active = {i for i, r in records.items() if not r.get('deleted')}
    if active != {d[0] for d in observed['docs']} or any(
        d[0] not in records or (d[1], d[3]) != (records[d[0]]['rel_path'], records[d[0]]['content_hash'])
        for d in observed['docs']
    ):
        raise ValueError('El espacio cambió desde index; reindexa antes de resolver')
    manifest = copy.deepcopy(original)
    updated = copy.deepcopy(current)
    updated['previous_paths'] = sorted(set(old.get('previous_paths', []) + current.get('previous_paths', []) + [old['rel_path']]) - {current['rel_path']})
    manifest['documents'][old_id] = updated
    del manifest['documents'][current_id]
    rewritten = {}
    for key, target in sorted(original['bindings'].items()):
        source, raw = json.loads(key)
        source = old_id if source == current_id else source
        target = old_id if target == current_id else target
        new_key = json.dumps([source, raw], ensure_ascii=False)
        if new_key in rewritten and rewritten[new_key] != target:
            raise ValueError('Bindings incompatibles: no se resolverá silenciosamente')
        rewritten[new_key] = target
    manifest['bindings'] = rewritten
    resolved = [c for c in manifest.get('conflicts', []) if c['id'] == old_id]
    manifest['conflicts'] = [c for c in manifest.get('conflicts', []) if c['id'] != old_id]
    manifest.setdefault('resolutions', []).append(dict(id=old_id, retired_id=current_id,
        old_path=old['rel_path'], rel_path=current['rel_path'], resolved_conflicts=resolved))
    prepared = index(workspace, _manifest=manifest, _prepare=True)
    if not any(d[0] == old_id and d[1] == current['rel_path'] for d in prepared['docs']):
        raise ValueError('El destino no pudo adoptar el UUID histórico; revisa colisiones')
    if any('UUID duplicado' in error for _, error in prepared['errors']):
        raise ValueError('Hay una colisión de UUID; resuélvela antes de aplicar')
    before = query(workspace, 'graph')['links']
    after = [dict(source=e[0], raw=e[1], target=e[2], status=e[3], candidates=json.loads(e[4]), needs_update=e[5]) for e in prepared['links']]
    def ordered(rows):
        return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))
    plan = dict(applied=False, surviving_id=old_id, retired_id=current_id,
                old_path=old['rel_path'], rel_path=current['rel_path'],
                records_before={old_id: old, current_id: current}, record_after=prepared['manifest']['documents'][old_id],
                bindings_before=original['bindings'], bindings_after=prepared['manifest']['bindings'],
                conflicts_resolved=resolved,
                document_changes=[dict(id=i, before=original['documents'].get(i),
                                       after=prepared['manifest']['documents'].get(i))
                                  for i in sorted(set(original['documents']) | set(prepared['manifest']['documents']))
                                  if original['documents'].get(i) != prepared['manifest']['documents'].get(i)],
                links_removed=ordered([r for r in before if r not in after]),
                links_added=ordered([r for r in after if r not in before]),
                errors=prepared['errors'])
    if apply:
        publish(state, prepared)
        plan['applied'] = True
    return plan
