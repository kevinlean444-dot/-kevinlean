"""Recarga y apertura explícitas; la creación nativa vive en notes.py."""
import os
import json
from pathlib import Path
import shlex
import stat
import sqlite3
import subprocess
import threading

from . import ui_contract
from .core import index
from .locking import SpaceBusy, RecoveryNeeded, space_lock


def reindex_space(workspace):
    try:
        result = index(workspace)
        return dict(ok=True, state='ready', result=result, error=None)
    except SpaceBusy:
        return dict(ok=False, state='busy', result=None, error='Espacio ocupado; reintenta después')
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        return dict(ok=False, state='index_error', result=None, error=str(exc))


def open_document(workspace, document, *, command=None, dry_run=False, runner=None):
    """Comando = lista argv o texto shlex; las variables/metacaracteres no se expanden."""
    try:
        if isinstance(document, str) and (Path(document).is_absolute() or '..' in Path(document).parts):
            raise ValueError('Ruta fuera del espacio')
        response = ui_contract.inspect_document(workspace, document, link_limit=1)
        if not response['ok']:
            return dict(ok=False, state=response['state'], argv=None, dry_run=dry_run, error=response['error']['message'])
        doc = response['data']['document']
        if doc is None or doc['deleted']:
            raise ValueError('Selecciona un documento activo')
        with space_lock(workspace, allow_recovery=False) as (root, state):
            current = json.loads((state / 'manifest.json').read_text(encoding='utf-8'))['documents'].get(doc['uuid'])
            if not current or current.get('deleted') or current['rel_path'] != doc['rel_path']:
                raise ValueError('El documento cambió de ubicación; actualiza la vista antes de abrirlo')
            relative = Path(doc['rel_path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Ruta fuera del espacio')
            path = root / relative
            if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root)):
                raise ValueError('No se permiten symlinks al abrir el editor')
            path = path.resolve(strict=True)
            if path == root or not path.is_relative_to(root) or not stat.S_ISREG(path.stat().st_mode):
                raise ValueError('Ruta fuera del espacio o archivo no regular')
            chosen = command if command is not None else os.environ.get('VISUAL') or os.environ.get('EDITOR') or ['xdg-open']
            if not isinstance(chosen, (str, list, tuple)):
                raise ValueError('Comando externo debe ser texto o lista de argumentos')
            argv = shlex.split(chosen) if isinstance(chosen, str) else list(chosen)
            if not argv or any(not isinstance(a, str) or not a or '\x00' in a for a in argv):
                raise ValueError('Comando externo vacío o inválido')
            argv.append(str(path))
            if not dry_run:
                process = (runner or subprocess.Popen)(argv, shell=False, close_fds=True, start_new_session=True)
                threading.Thread(target=process.wait, name='trama-editor-reaper', daemon=True).start()
            return dict(ok=True, state='ready', argv=argv, dry_run=dry_run, error=None)
    except SpaceBusy:
        state, message = 'busy', 'Espacio ocupado; reintenta después'
    except RecoveryNeeded:
        state, message = 'recovery_needed', 'Hay una publicación pendiente'
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        state, message = 'open_error', str(exc)
    return dict(ok=False, state=state, argv=None, dry_run=dry_run, error=message)
