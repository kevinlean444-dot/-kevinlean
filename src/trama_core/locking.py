"""Bloqueos cooperativos Linux por espacio; ninguna espera indefinida."""
from contextlib import contextmanager
import fcntl
import os
import stat


class SpaceBusy(RuntimeError):
    pass


class RecoveryNeeded(RuntimeError):
    pass


@contextmanager
def space_lock(workspace, *, exclusive=False, allow_recovery=True):
    # Local import avoids a core/locking import cycle.
    from .core import recover, root_state
    # Do not inspect staging files while another process may be replacing them.
    root, state = root_state(workspace, create=exclusive, check_files=False)
    if (state / '.lock').is_symlink():
        raise ValueError('Archivo de bloqueo inseguro')
    fd = os.open(state / '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Archivo de bloqueo inseguro')
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(fd, mode | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SpaceBusy('Espacio ocupado: otra operación mantiene el bloqueo') from exc
        # Validate again under the lock before recovery or reading paired files.
        root_state(workspace)
        if (state / 'pending').exists():
            if not allow_recovery:
                raise RecoveryNeeded('Hay una publicación pendiente; ejecuta index para recuperarla')
            if not exclusive:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise SpaceBusy('Espacio ocupado: no se pudo adquirir bloqueo para recuperar') from exc
            recover(state)
            if not exclusive:
                fcntl.flock(fd, fcntl.LOCK_SH)
        yield root, state
    finally:
        # Closing this independent descriptor releases flock even after exceptions.
        os.close(fd)
