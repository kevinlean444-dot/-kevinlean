"""Backend GTK 4 opcional. Toda consulta se ejecuta en un worker secuencial."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk

from . import Presenter, link_text, notices, status_text


def available():
    return Gtk.init_check()


def label(text='', *, css=None):
    widget = Gtk.Label(label=text, xalign=0, wrap=True, selectable=True)
    if css:
        widget.add_css_class(css)
    return widget


def clear(box):
    child = box.get_first_child()
    while child:
        following = child.get_next_sibling()
        box.remove(child)
        child = following


def scroller(child):
    scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(child)
    return scroll


class Window(Gtk.ApplicationWindow):
    def __init__(self, application, workspace, query='', select=None):
        super().__init__(application=application, title='Trama · Lectura local')
        self.set_default_size(1120, 760)
        self.add_css_class('trama')
        self.controller = Presenter(workspace)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='trama-reader')
        self.closed = False
        self.pending = 0
        self.ticket = 0
        self.debounce = None
        self.snapshot = None
        self.worker_error = None
        self.result_buttons, self.result_labels = [], []
        self.backlink_buttons, self.backlink_labels, self.outgoing_labels = [], [], []
        self.connect('close-request', self.on_close)
        provider = Gtk.CssProvider()
        provider.load_from_path(str(Path(__file__).with_name('style.css')))
        Gtk.StyleContext.add_provider_for_display(self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.css_provider = provider

        header = Gtk.HeaderBar()
        header.set_title_widget(label('Trama · Tu espacio de lectura', css='section'))
        self.back_button = Gtk.Button(label='Atrás', sensitive=False)
        self.back_button.connect('clicked', lambda _: self.submit('back'))
        header.pack_start(self.back_button)
        refresh = Gtk.Button(label='Actualizar')
        refresh.set_tooltip_text('Volver a consultar el índice sin modificar notas')
        refresh.connect('clicked', lambda _: self.submit('refresh'))
        header.pack_end(refresh)
        self.set_titlebar(header)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.banner = label(css='warning')
        self.banner.set_visible(False)
        root.append(self.banner)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True)
        paned.set_position(350)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(left, f'set_margin_{side}')(12)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_property('placeholder-text', 'Buscar en tus notas…')
        self.search_entry.set_text(query)
        self.search_entry.connect('search-changed', self.search_changed)
        left.append(self.search_entry)
        self.results_count = label('Buscando…', css='muted')
        left.append(self.results_count)
        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left.append(scroller(self.results_box))
        paned.set_start_child(left)
        paned.set_resize_start_child(False)
        paned.set_shrink_start_child(False)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(right, f'set_margin_{side}')(12)
        self.title_label = label('Elige una nota', css='title')
        self.metadata_label = label('Busca texto para explorar tus relaciones locales.', css='muted')
        right.append(self.title_label)
        right.append(self.metadata_label)
        notebook = Gtk.Notebook(vexpand=True)
        self.backlinks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.outgoing_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.health_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for box, title in ((self.backlinks_box, 'Backlinks'), (self.outgoing_box, 'Enlaces salientes'), (self.health_box, 'Avisos')):
            box.add_css_class('paper')
            notebook.append_page(scroller(box), Gtk.Label(label=title))
        right.append(notebook)
        paned.set_end_child(right)
        root.append(paned)
        self.status_label = label('Cargando estado…', css='statusbar')
        root.append(self.status_label)
        self.set_child(root)
        self.submit('refresh', query=query, select=select)

    def submit(self, operation, *args, **kwargs):
        if self.closed:
            return
        self.ticket += 1
        ticket = self.ticket
        self.pending += 1
        def work():
            getattr(self.controller, operation)(*args, **kwargs)
            return self.controller.snapshot()
        future = self.executor.submit(work)
        future.add_done_callback(lambda task: GLib.idle_add(self.complete, task, ticket))

    def complete(self, future, ticket):
        self.pending -= 1
        if self.closed:
            return GLib.SOURCE_REMOVE
        try:
            snapshot = future.result()
        except Exception as exc:
            self.worker_error = str(exc)
            self.banner.set_text('No se pudo completar la lectura. Usa Actualizar para reintentar.')
            self.banner.set_visible(True)
            return GLib.SOURCE_REMOVE
        if ticket == self.ticket:
            self.worker_error = None
            self.snapshot = snapshot
            self.render(snapshot)
        return GLib.SOURCE_REMOVE

    def search_changed(self, entry):
        if self.debounce:
            GLib.source_remove(self.debounce)
        text = entry.get_text()
        def search():
            self.debounce = None
            self.submit('search', text)
            return GLib.SOURCE_REMOVE
        self.debounce = GLib.timeout_add(200, search)

    def render(self, snapshot):
        messages = notices(snapshot)
        self.banner.set_text('\n'.join(messages))
        self.banner.set_visible(bool(messages))
        self.status_label.set_text(status_text(snapshot['status']))
        if snapshot['status'] and not snapshot['status']['ok']:
            self.status_label.add_css_class('warning')
        else:
            self.status_label.remove_css_class('warning')
        self.back_button.set_sensitive(bool(snapshot['history']))
        clear(self.results_box)
        self.result_buttons, self.result_labels = [], []
        response = snapshot['search']
        if response and response['ok']:
            self.results_count.set_text(f"{response['data']['total']} resultados · {snapshot['query']}")
            for doc in response['data']['results']:
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                title = label(doc['title'], css='section')
                text = label(f"{doc['rel_path']}\n{doc['snippet']}", css='muted')
                box.append(title)
                box.append(text)
                if doc['has_conflicts'] or doc['needs_update_count']:
                    box.append(label(f"{doc['needs_update_count']} enlaces por actualizar" + (' · Conflicto' if doc['has_conflicts'] else ''), css='warning'))
                button = Gtk.Button(child=box)
                button.connect('clicked', lambda _, identity=doc['uuid']: self.submit('select', identity))
                self.results_box.append(button)
                self.result_buttons.append(button)
                self.result_labels.append(title)
        else:
            self.results_count.set_text('Búsqueda no disponible')
        clear(self.backlinks_box)
        clear(self.outgoing_box)
        clear(self.health_box)
        self.backlink_buttons, self.backlink_labels, self.outgoing_labels = [], [], []
        inspect = snapshot['inspection']
        if not inspect:
            return
        if not inspect['ok']:
            self.title_label.set_text('No se pudo abrir la nota')
            self.metadata_label.set_text(inspect['error']['message'])
            return
        data = inspect['data']
        doc = data['document']
        if doc:
            self.title_label.set_text(doc['title'])
            self.metadata_label.set_text(f"{doc['rel_path']}\nUUID: {doc['uuid']}\nIdentidad: {doc['identity_origin']} · " + ('Indexada' if doc['indexed'] else 'No indexada'))
        else:
            self.title_label.set_text('Archivo sin identidad indexada')
            self.metadata_label.set_text('Revisa los avisos de lectura.')
        for direction, box in (('backlinks', self.backlinks_box), ('outgoing_links', self.outgoing_box)):
            if not data[direction]:
                box.append(label('Sin enlaces en esta sección', css='muted'))
            for n, link in enumerate(data[direction]):
                text = label(link_text(link, direction))
                button = Gtk.Button(child=text)
                button.set_sensitive(direction == 'backlinks' or link['status'] == 'resolved')
                if link['needs_update']:
                    text.add_css_class('warning')
                elif link['status'] == 'ambiguous':
                    text.add_css_class('ambiguous')
                elif link['status'] in ('unresolved', 'outside', 'invalid'):
                    text.add_css_class('broken')
                button.connect('clicked', lambda _, d=direction, i=n: self.submit('navigate', d, i))
                box.append(button)
                if direction == 'backlinks':
                    self.backlink_buttons.append(button)
                    self.backlink_labels.append(text)
                else:
                    self.outgoing_labels.append(text)
        health = data['health']
        for error in health['errors']:
            self.health_box.append(label(f"{error['path']}: {error['error']}", css='warning'))
        for conflict in health['conflicts']:
            self.health_box.append(label(f"Conflicto: {conflict['old_path']} → {', '.join(conflict['candidates'])}", css='ambiguous'))
        if not health['errors'] and not health['conflicts']:
            self.health_box.append(label('Sin errores de indexación ni conflictos para esta nota.'))

    def on_close(self, *_):
        self.closed = True
        if self.debounce:
            GLib.source_remove(self.debounce)
            self.debounce = None
        self.executor.shutdown(wait=False, cancel_futures=True)
        return False


def run(workspace, query='', select=None, *, smoke_test=False):
    if not available():
        raise RuntimeError('GTK 4 no tiene un display disponible; usa --backend snapshot o Xvfb')
    app = Gtk.Application(application_id='io.trama.Reader', flags=Gio.ApplicationFlags.NON_UNIQUE)
    result = dict(report=None, error=None)
    def activate(application):
        window = Window(application, workspace, query, select)
        window.present()
        if not smoke_test:
            return
        deadline = GLib.get_monotonic_time() + 10_000_000
        selected_from_widget = False
        def smoke():
            nonlocal selected_from_widget
            try:
                if window.pending or not window.snapshot or window.debounce:
                    if GLib.get_monotonic_time() > deadline:
                        raise RuntimeError('Timeout cargando los widgets GTK')
                    return GLib.SOURCE_CONTINUE
                if window.worker_error:
                    raise RuntimeError(window.worker_error)
                state = window.snapshot
                if not state['status']['ok'] or not state['search']['ok']:
                    raise RuntimeError('El contrato no está listo: ' + '; '.join(notices(state)))
                rows = state['search']['data']['results']
                if not selected_from_widget:
                    chosen = next((i for i, row in enumerate(rows) if select in (row['uuid'], row['rel_path'])), 0)
                    if rows and (not select or select in (rows[chosen]['uuid'], rows[chosen]['rel_path'])):
                        window.result_buttons[chosen].emit('clicked')
                        selected_from_widget = True
                        return GLib.SOURCE_CONTINUE
                    selected_from_widget = True
                if not state['inspection'] or not state['inspection']['ok'] or state['inspection']['data']['document'] is None:
                    raise RuntimeError('Smoke test requiere una nota real: usa --query o --select')
                data = state['inspection']['data']
                doc = data['document']
                assert window.title_label.get_text() == doc['title'], 'Título no renderizado'
                assert doc['uuid'] in window.metadata_label.get_text(), 'UUID no renderizado'
                assert window.title_label.get_root() == window and window.title_label.get_mapped(), 'Ventana no visible'
                assert str(state['status']['data']['counts']['notes']) + ' notas' in window.status_label.get_text(), 'Estado no renderizado'
                assert [w.get_text() for w in window.result_labels] == [d['title'] for d in rows], 'Resultados no renderizados'
                assert [w.get_text() for w in window.backlink_labels] == [link_text(e, 'backlinks') for e in data['backlinks']], 'Backlinks no renderizados'
                assert [w.get_text() for w in window.outgoing_labels] == [link_text(e, 'outgoing_links') for e in data['outgoing_links']], 'Salientes no renderizados'
                result['report'] = dict(backend='gtk', gtk_version=[Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()],
                                        title=doc['title'], uuid=doc['uuid'], results=len(rows), backlinks=len(data['backlinks']),
                                        backlink_texts=[w.get_text() for w in window.backlink_labels],
                                        outgoing_texts=[w.get_text() for w in window.outgoing_labels],
                                        status=window.status_label.get_text(), mapped=window.title_label.get_mapped(), verified=True)
            except Exception as exc:
                result['error'] = str(exc)
            window.close()
            application.quit()
            return GLib.SOURCE_REMOVE
        GLib.timeout_add(25, smoke)
    app.connect('activate', activate)
    code = app.run(['trama'])
    if result['error']:
        raise RuntimeError(result['error'])
    if code:
        raise RuntimeError(f'GTK terminó con código {code}')
    if smoke_test and not result['report']:
        raise RuntimeError('GTK terminó sin completar el smoke test')
    return result['report']
