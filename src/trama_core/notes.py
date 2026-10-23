"""Creación explícita de notas nativas; nunca modifica archivos existentes."""
import json
import os
from pathlib import Path
import sqlite3
import uuid

from .core import _index, publish
from .locking import space_lock, SpaceBusy


def create_note(workspace, name):
    """Los directorios padres deben existir. El UUID se escribe solo en el archivo nuevo.

    Si falla la indexación se conserva la nota: el usuario puede reintentar index.
    Los descriptores de directorio impiden atravesar symlinks durante la creación.
    """
    created = False
    identity = relative = None
    try:
        if not isinstance(name, str) or not name.strip() or any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise ValueError('Indica un título o ruta relativa sin caracteres de control')
        path = Path(name)
        if not path.parts or path.is_absolute() or any(p in ('.', '..') or p.startswith('.') for p in path.parts):
            raise ValueError('Usa una ruta relativa visible dentro del espacio')
        if path.suffix.lower() != '.md':
            path = Path(str(path) + '.md')
        title = path.stem
        if not title.strip():
            raise ValueError('El título no puede estar vacío')
        relative = path.as_posix()
        with space_lock(workspace, exclusive=True) as (root, state):
            # Valida el estado previo antes de crear un documento irreversible.
            prepared = _index(workspace, _prepare=True)
            identity = str(uuid.uuid4())
            if identity in prepared['manifest']['documents']:
                raise ValueError('Colisión de UUID; reintenta la creación')
            content = f'---\nid: {identity}\ntitle: {json.dumps(title, ensure_ascii=False)}\n---\n\n# {title}\n'
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                for part in path.parts[:-1]:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
                    os.close(directory)
                    directory = child
                # También rechaza symlinks finales (incluso colgantes), sin truncarlos.
                fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                             0o600, dir_fd=directory)
                created = True
                with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.fsync(directory)
            finally:
                os.close(directory)
            prepared = _index(workspace, _prepare=True)
            if not any(row[0] == identity and row[1] == relative for row in prepared['docs']):
                raise ValueError('Nota creada, pero no indexada; consulta index y sus errores')
            publish(state, prepared)
            result = dict(documents=len(prepared['docs']), links=len(prepared['links']),
                          errors=[dict(path=p, error=e) for p, e in prepared['errors']])
        return dict(ok=True, state='ready', created=True, uuid=identity, rel_path=relative,
                    title=title, identity_source='frontmatter', result=result, error=None)
    except SpaceBusy:
        message = 'Espacio ocupado; reintenta después'
        status = 'busy'
    except FileExistsError:
        message = 'La ruta ya existe; no se ha sobrescrito ningún archivo'
        status = 'already_exists'
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        message = str(exc)
        status = 'index_error' if created else 'create_error'
    if created:
        message += '; se conserva el archivo nuevo: revisa su contenido y ejecuta index'
    return dict(ok=False, state=status, created=created, uuid=identity, rel_path=relative, error=message)
