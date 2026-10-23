"""Carga diferida de GTK: snapshot/TUI no necesitan importar gi."""
import json
import os

from .terminal import run as run_terminal


def run(workspace, *, backend='auto', query='', select=None, smoke_test=False, page_size=50, link_page_size=50, editor=None, editor_dry_run=False, health_filter=None):
    from ..health import CATEGORIES
    if health_filter is not None and health_filter not in CATEGORIES:
        raise ValueError('Filtro de salud inválido')
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError('page_size debe estar entre 1 y 100')
    if type(link_page_size) is not int or not 1 <= link_page_size <= 100:
        raise ValueError('link_page_size debe estar entre 1 y 100')
    if smoke_test and backend not in ('gtk', 'auto'):
        raise ValueError('--smoke-test requiere backend gtk o auto')
    if backend in ('auto', 'gtk') and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        if backend == 'gtk' or smoke_test:
            raise RuntimeError('No hay display GTK disponible; usa Xvfb o --backend snapshot')
        backend = 'tui'
    if backend in ('auto', 'gtk'):
        try:
            from . import gtk
        except (ImportError, ValueError) as exc:
            if backend == 'gtk' or smoke_test:
                raise RuntimeError('GTK 4/PyGObject no disponible para este Python; consulta docs/ui-window.md') from exc
        else:
            if gtk.available():
                report = gtk.run(workspace, query, select, smoke_test=smoke_test, page_size=page_size, link_page_size=link_page_size, editor=editor, editor_dry_run=editor_dry_run, health_filter=health_filter)
                if report:
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0
            if backend == 'gtk' or smoke_test:
                raise RuntimeError('No hay display GTK disponible; usa Xvfb o --backend snapshot')
        backend = 'tui'
    return run_terminal(workspace, query, select, snapshot=backend == 'snapshot', page_size=page_size, link_page_size=link_page_size, editor=editor, editor_dry_run=editor_dry_run, health_filter=health_filter)
