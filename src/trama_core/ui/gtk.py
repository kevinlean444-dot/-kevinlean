"""Backend GTK 4 opcional. Toda consulta se ejecuta en un worker secuencial."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk

from . import FOCUS_ORDER, Presenter, link_text, notices, status_text, page_text, link_page_text, issue_text, health_page_text, issue_caption


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
    def __init__(self, application, workspace, query='', select=None, *, page_size=50, link_page_size=50, editor=None, editor_dry_run=False, health_filter=None):
        super().__init__(application=application, title='Trama · Lectura local')
        self.set_default_size(1120, 760)
        self.add_css_class('trama')
        self.controller = Presenter(workspace, page_size=page_size, link_page_size=link_page_size, editor=editor, editor_dry_run=editor_dry_run)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='trama-reader')
        self.closed = False
        self.pending = 0
        self.ticket = 0
        self.jobs = []
        self.running = False
        self.focus_after_update = 'search'
        self.rendered_search = object()
        self.rendered_inspection = object()
        self.rendered_creation = None
        self.syncing_view = False
        self.debounce = None
        self.snapshot = None
        self.worker_error = None
        self.result_buttons, self.result_labels = [], []
        self.backlink_buttons, self.backlink_labels, self.outgoing_labels, self.outgoing_buttons = [], [], [], []
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
        self.refresh_button = refresh
        self.reindex_button = Gtk.Button(label='Reindexar')
        self.reindex_button.set_tooltip_text('Actualizar índice y manifiesto sin escribir notas · Ctrl+Shift+R')
        self.reindex_button.connect('clicked', lambda _: self.submit('reindex'))
        header.pack_end(self.reindex_button)
        self.open_button = Gtk.Button(label='Abrir editor', sensitive=False)
        self.open_button.connect('clicked', lambda _: self.submit('open_external'))
        header.pack_end(self.open_button)
        self.new_button = Gtk.Button(label='Nueva nota')
        self.new_button.set_tooltip_text('Crear una nota nativa · Ctrl+N')
        self.new_button.connect('clicked', lambda _: self.show_new_note())
        header.pack_start(self.new_button)
        self.creation_dialog = None
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
        self.view_filter = Gtk.DropDown.new_from_strings(['Búsqueda', 'all', 'needs_update', 'broken', 'ambiguous', 'conflicts'])
        self.view_filter.set_tooltip_text('Cola de mantenimiento · Ctrl+H recorre filtros · Ctrl+F vuelve a búsqueda')
        def change_view(widget, _):
            if self.syncing_view:
                return
            selected = widget.get_selected()
            if selected == 0:
                self.submit('show_search')
            else:
                self.submit('show_health', ('all', 'needs_update', 'broken', 'ambiguous', 'conflicts')[selected - 1])
        self.view_filter.connect('notify::selected', change_view)
        left.append(self.view_filter)
        self.results_count = label('Buscando…', css='muted')
        left.append(self.results_count)
        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.results_box.set_focusable(True)
        left.append(scroller(self.results_box))
        paging = Gtk.Box(spacing=8)
        self.previous_page = Gtk.Button(label='Página anterior', sensitive=False)
        self.next_page = Gtk.Button(label='Página siguiente', sensitive=False)
        self.previous_page.connect('clicked', lambda _: self.submit('change_page', -1))
        self.next_page.connect('clicked', lambda _: self.submit('change_page', 1))
        paging.append(self.previous_page)
        paging.append(self.next_page)
        left.append(paging)
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
        self.issue_details = label(css='warning')
        self.issue_details.set_selectable(True)
        self.issue_details.set_visible(False)
        right.append(self.issue_details)
        notebook = Gtk.Notebook(vexpand=True)
        self.notebook = notebook
        self.backlinks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.outgoing_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.health_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.link_controls = {}
        self.inspector_panels = {}
        for section, box, title in (('backlinks', self.backlinks_box, 'Backlinks'), ('outgoing_links', self.outgoing_box, 'Enlaces salientes'), ('health', self.health_box, 'Avisos')):
            box.add_css_class('paper')
            box.set_focusable(True)
            panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.inspector_panels[section] = panel
            if section != 'health':
                controls = Gtk.Box(spacing=6)
                count = label('Sin enlaces', css='muted')
                controls.append(count)
                prev = Gtk.Button(label='Anterior', sensitive=False)
                nxt = Gtk.Button(label='Siguiente', sensitive=False)
                prev.connect('clicked', lambda _, d=section: self.submit('change_link_page', d, -1))
                nxt.connect('clicked', lambda _, d=section: self.submit('change_link_page', d, 1))
                controls.append(prev)
                controls.append(nxt)
                panel.append(controls)
                self.link_controls[section] = dict(count=count, previous=prev, next=nxt)
            panel.append(scroller(box))
            notebook.append_page(panel, Gtk.Label(label=title))
        right.append(notebook)
        paned.set_end_child(right)
        root.append(paned)
        self.status_label = label('Cargando estado…', css='statusbar')
        root.append(self.status_label)
        self.set_child(root)
        self.key_controller = Gtk.EventControllerKey()
        self.key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.key_controller.connect('key-pressed', self.key_pressed)
        self.add_controller(self.key_controller)
        self.submit('refresh', query=query, select=select)
        if health_filter is not None:
            self.submit('show_health', health_filter)

    def show_new_note(self):
        if self.creation_dialog is not None:
            self.creation_dialog.present()
            return
        dialog = Gtk.Window(title='Nueva nota nativa', transient_for=self, modal=True)
        dialog.set_default_size(420, 140)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ('start', 'end', 'top', 'bottom'):
            getattr(box, 'set_margin_' + side)(16)
        entry = Gtk.Entry(placeholder_text='Título o ruta relativa.md')
        box.append(entry)
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cancel = Gtk.Button(label='Cancelar')
        confirm = Gtk.Button(label='Crear')
        buttons.append(cancel)
        buttons.append(confirm)
        box.append(buttons)
        dialog.set_child(box)
        dialog.set_default_widget(confirm)
        self.creation_dialog, self.creation_entry, self.creation_confirm = dialog, entry, confirm
        def finish(create=False):
            name = entry.get_text()
            self.creation_dialog = None
            dialog.destroy()
            if create:
                self.submit('create_note', name)
        cancel.connect('clicked', lambda _: finish())
        confirm.connect('clicked', lambda _: finish(True))
        entry.connect('activate', lambda _: finish(True))
        def close_request(_):
            finish()
            return True
        dialog.connect('close-request', close_request)
        keys = Gtk.EventControllerKey()
        def key_pressed(_, keyval, keycode, modifiers):
            if keyval == Gdk.KEY_Escape:
                finish()
                return True
            return False
        keys.connect('key-pressed', key_pressed)
        dialog.add_controller(keys)
        dialog.present()
        entry.grab_focus()

    def submit(self, operation, *args, **kwargs):
        if self.closed:
            return
        self.ticket += 1
        job = [operation, args, kwargs, self.ticket]
        if (self.jobs and self.jobs[-1][0] == operation and operation in ('search', 'set_focus', 'move_result', 'move_link', 'refresh', 'reindex')
                and (operation != 'move_link' or self.jobs[-1][1][0] == args[0])):
            previous = self.jobs[-1]
            if operation == 'move_result':
                job[1] = (previous[1][0] + args[0],)
            elif operation == 'move_link' and previous[1][0] == args[0]:
                job[1] = (args[0], previous[1][1] + args[1])
            self.jobs[-1] = job
        elif len(self.jobs) < 16:
            self.jobs.append(job)
        else:
            self.ticket -= 1
            self.banner.set_text('Hay acciones pendientes; vuelve a intentarlo en un momento.')
            self.banner.set_visible(True)
            return
        self.pending = int(self.running) + len(self.jobs)
        self.launch_next()

    def launch_next(self):
        if self.running or self.closed or not self.jobs:
            return
        operation, args, kwargs, ticket = self.jobs.pop(0)
        self.running = True
        self.pending = 1 + len(self.jobs)
        def work():
            getattr(self.controller, operation)(*args, **kwargs)
            return self.controller.snapshot()
        future = self.executor.submit(work)
        future.add_done_callback(lambda task: GLib.idle_add(self.complete, task, ticket))

    def complete(self, future, ticket):
        self.running = False
        self.pending = len(self.jobs)
        if self.closed:
            return GLib.SOURCE_REMOVE
        try:
            snapshot = future.result()
        except Exception as exc:
            self.worker_error = str(exc)
            self.banner.set_text('No se pudo completar la lectura. Usa Actualizar para reintentar.')
            self.banner.set_visible(True)
        else:
            if ticket == self.ticket:
                self.worker_error = None
                self.snapshot = snapshot
                self.render(snapshot)
        self.launch_next()
        return GLib.SOURCE_REMOVE

    def focus_group(self):
        focus = self.get_focus()
        panels = [('search', self.search_entry), ('results', self.results_box),
                  ('backlinks', self.inspector_panels['backlinks']), ('outgoing_links', self.inspector_panels['outgoing_links']), ('health', self.inspector_panels['health'])]
        for group, widget in panels:
            if focus == widget or (focus and focus.is_ancestor(widget)):
                return group
        return 'navigation'

    def focus_panel(self, group, *, select_text=False):
        state = self.snapshot or {}
        if group == 'search':
            if self.focus_group() != 'search':
                self.search_entry.grab_focus()
            if select_text:
                self.search_entry.select_region(0, -1)
        elif group == 'results':
            position = max(0, state.get('health_cursor', -1) if state.get('health_view') else state.get('result_cursor', 0))
            target = self.result_buttons[min(position, len(self.result_buttons) - 1)] if self.result_buttons else self.results_box
            target.grab_focus()
        elif group in ('backlinks', 'outgoing_links', 'health'):
            self.notebook.set_current_page({'backlinks': 0, 'outgoing_links': 1, 'health': 2}[group])
            buttons = self.backlink_buttons if group == 'backlinks' else self.outgoing_buttons if group == 'outgoing_links' else []
            position = max(0, state.get('link_cursors', {}).get(group, 0))
            box = {'backlinks': self.backlinks_box, 'outgoing_links': self.outgoing_box, 'health': self.health_box}[group]
            (buttons[min(position, len(buttons) - 1)] if buttons else box).grab_focus()
        else:
            (self.back_button if self.back_button.get_sensitive() else self.refresh_button).grab_focus()

    def key_pressed(self, controller, keyval, keycode, modifiers):
        control = bool(modifiers & Gdk.ModifierType.CONTROL_MASK)
        alt = bool(modifiers & Gdk.ModifierType.ALT_MASK)
        shift = bool(modifiers & Gdk.ModifierType.SHIFT_MASK)
        focus = self.get_focus()
        editing = isinstance(focus, Gtk.Editable) and focus.get_editable()
        group = self.focus_group()
        if keyval == Gdk.KEY_F5 or (control and keyval in (Gdk.KEY_r, Gdk.KEY_R)):
            self.submit('reindex' if control and shift and keyval in (Gdk.KEY_r, Gdk.KEY_R) else 'refresh')
            return True
        if control and keyval in (Gdk.KEY_h, Gdk.KEY_H):
            categories = ('all', 'needs_update', 'broken', 'ambiguous', 'conflicts')
            state = self.snapshot or {}
            category = categories[(categories.index(state.get('health_filter', 'all')) + 1) % len(categories)] if state.get('health_view') else 'all'
            self.focus_after_update = 'results'
            self.submit('show_health', category)
            return True
        if control and keyval in (Gdk.KEY_n, Gdk.KEY_N):
            self.show_new_note()
            return True
        if control and keyval in (Gdk.KEY_o, Gdk.KEY_O):
            self.submit('open_external')
            return True
        if (control and keyval in (Gdk.KEY_f, Gdk.KEY_F)) or (keyval == Gdk.KEY_slash and not editing):
            self.submit('show_search')
            self.focus_panel('search', select_text=True)
            self.submit('set_focus', 'search')
            return True
        if (alt and keyval == Gdk.KEY_Left) or (keyval == Gdk.KEY_BackSpace and not editing):
            self.submit('back')
            return True
        if keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            target = FOCUS_ORDER[(FOCUS_ORDER.index(group) + (-1 if shift or keyval == Gdk.KEY_ISO_Left_Tab else 1)) % len(FOCUS_ORDER)]
            self.focus_panel(target)
            self.submit('set_focus', target)
            return True
        if group == 'navigation' and keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
            buttons = [button for button in (self.back_button, self.refresh_button, self.reindex_button, self.open_button, self.new_button, self.previous_page, self.next_page) if button.get_sensitive()]
            current = next((i for i, button in enumerate(buttons) if button == focus or (focus and focus.is_ancestor(button))), 0)
            buttons[(current + (1 if keyval == Gdk.KEY_Right else -1)) % len(buttons)].grab_focus()
            return True
        if keyval == Gdk.KEY_Escape:
            text = self.search_entry.get_text()
            if text:
                self.search_entry.set_text('')
            self.focus_after_update = 'search'
            self.submit('escape', text=text, focus=group)
            return True
        if keyval in (Gdk.KEY_Page_Down, Gdk.KEY_Page_Up) and group in ('backlinks', 'outgoing_links') and not control:
            self.focus_after_update = group
            self.submit('change_link_page', group, 1 if keyval == Gdk.KEY_Page_Down else -1)
            return True
        if keyval in (Gdk.KEY_Page_Down, Gdk.KEY_Page_Up) and (group == 'results' or control):
            self.focus_after_update = 'results'
            self.submit('change_page', 1 if keyval == Gdk.KEY_Page_Down else -1)
            return True
        if keyval in (Gdk.KEY_Down, Gdk.KEY_Up) and group in ('search', 'results', 'backlinks', 'outgoing_links'):
            delta = 1 if keyval == Gdk.KEY_Down else -1
            target = 'results' if group == 'search' else group
            self.focus_after_update = target
            if target == 'results':
                self.submit('move_result', delta)
            else:
                self.submit('move_link', target, delta)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and group in ('search', 'results', 'backlinks', 'outgoing_links'):
            if group in self.link_controls and focus in (self.link_controls[group]['previous'], self.link_controls[group]['next']):
                return False
            target = 'results' if group == 'search' else group
            self.focus_after_update = target
            buttons = self.result_buttons if target == 'results' else self.backlink_buttons if target == 'backlinks' else self.outgoing_buttons
            position = next((i for i, button in enumerate(buttons) if focus == button or (focus and focus.is_ancestor(button))), None)
            if position is not None:
                self.submit('select_result', position) if target == 'results' else self.submit('navigate', target, position)
            else:
                self.submit('activate', target)
            return True
        return False

    def search_changed(self, entry):
        if self.debounce:
            GLib.source_remove(self.debounce)
        text = entry.get_text()
        def search():
            self.debounce = None
            self.submit('show_search')
            self.submit('search', text)
            return GLib.SOURCE_REMOVE
        self.debounce = GLib.timeout_add(200, search)

    def render(self, snapshot):
        creation = snapshot.get('creation_action')
        if creation and creation['ok'] and creation['uuid'] != self.rendered_creation:
            self.rendered_creation = creation['uuid']
            self.focus_after_update = 'results'
            if self.search_entry.get_text() != snapshot['query']:
                self.search_entry.set_text(snapshot['query'])
        messages = notices(snapshot)
        self.banner.set_text('\n'.join(messages))
        self.banner.set_visible(bool(messages))
        self.status_label.set_text(status_text(snapshot['status']))
        if snapshot['status'] and not snapshot['status']['ok']:
            self.status_label.add_css_class('warning')
        else:
            self.status_label.remove_css_class('warning')
        self.back_button.set_sensitive(bool(snapshot['history']))
        previous_focus = self.get_focus()
        group = self.focus_after_update or self.focus_group()
        self.focus_after_update = None
        view = (snapshot['health_view'], snapshot['health_response'] if snapshot['health_view'] else snapshot['search'])
        if view != self.rendered_search:
            self.rendered_search = view
            self.render_results(snapshot)
        if snapshot['inspection'] != self.rendered_inspection:
            self.rendered_inspection = snapshot['inspection']
            self.render_inspector(snapshot)
        issue = snapshot['selected_issue']
        self.issue_details.set_text(issue_text(issue) if issue else '')
        self.issue_details.set_visible(issue is not None)
        self.syncing_view = True
        self.view_filter.set_selected(1 + ('all', 'needs_update', 'broken', 'ambiguous', 'conflicts').index(snapshot['health_filter']) if snapshot['health_view'] else 0)
        self.syncing_view = False
        for i, button in enumerate(self.result_buttons):
            if i == (snapshot['health_cursor'] if snapshot['health_view'] else snapshot['result_cursor']):
                button.add_css_class('selected-result')
            else:
                button.remove_css_class('selected-result')
        if group == 'navigation' and previous_focus in (self.back_button, self.refresh_button, self.reindex_button, self.open_button, self.new_button, self.previous_page, self.next_page) and previous_focus.get_sensitive():
            previous_focus.grab_focus()
        else:
            self.focus_panel(group)
        if snapshot['close_requested']:
            self.close()

    def render_results(self, snapshot):
        clear(self.results_box)
        self.result_buttons, self.result_labels = [], []
        if snapshot['health_view']:
            response = snapshot['health_response']
            self.results_count.set_text(health_page_text(snapshot))
            self.previous_page.set_sensitive(bool(response and response['ok'] and response['data']['offset'] > 0))
            self.next_page.set_sensitive(bool(response and response['ok'] and response['data']['next_offset'] is not None and response['data']['next_offset'] <= 1000000))
            for i, issue in enumerate(response['data']['items'] if response and response['ok'] else []):
                text = label(issue_caption(issue))
                button = Gtk.Button(child=text)
                button.connect('clicked', lambda _, position=i: self.submit('select_issue', position))
                self.results_box.append(button)
                self.result_buttons.append(button)
                self.result_labels.append(text)
            return
        response = snapshot['search']
        if response and response['ok']:
            self.results_count.set_text(page_text(snapshot))
            self.previous_page.set_sensitive(snapshot['offset'] > 0)
            self.next_page.set_sensitive(response['data']['next_offset'] is not None and response['data']['next_offset'] <= 10000)
            for i, doc in enumerate(response['data']['results']):
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                title = label(doc['title'], css='section')
                text = label(f"{doc['rel_path']}\n{doc['snippet']}", css='muted')
                box.append(title)
                box.append(text)
                if doc['has_conflicts'] or doc['needs_update_count']:
                    box.append(label(f"{doc['needs_update_count']} enlaces por actualizar" + (' · Conflicto' if doc['has_conflicts'] else ''), css='warning'))
                button = Gtk.Button(child=box)
                button.connect('clicked', lambda _, position=i: self.submit('select_result', position))
                self.results_box.append(button)
                self.result_buttons.append(button)
                self.result_labels.append(title)
        else:
            self.results_count.set_text('Búsqueda no disponible')
            self.previous_page.set_sensitive(False)
            self.next_page.set_sensitive(False)

    def render_inspector(self, snapshot):
        clear(self.backlinks_box)
        clear(self.outgoing_box)
        clear(self.health_box)
        self.backlink_buttons, self.backlink_labels, self.outgoing_labels, self.outgoing_buttons = [], [], [], []
        inspect = snapshot['inspection']
        for controls in self.link_controls.values():
            controls['count'].set_text('Enlaces no disponibles')
            controls['previous'].set_sensitive(False)
            controls['next'].set_sensitive(False)
        self.open_button.set_sensitive(bool(inspect and inspect['ok'] and inspect['data']['document'] and not inspect['data']['document']['deleted']))
        if not inspect:
            return
        if not inspect['ok']:
            self.title_label.set_text('No se pudo abrir la nota')
            self.metadata_label.set_text(inspect['error']['message'])
            return
        data = inspect['data']
        for section, controls in self.link_controls.items():
            page = data['link_pages'][section]
            controls['count'].set_text(link_page_text(snapshot, section))
            controls['previous'].set_sensitive(page['offset'] > 0)
            controls['next'].set_sensitive(page['next_offset'] is not None and page['next_offset'] <= 1000000)
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
                button.set_tooltip_text('Abrir nota' if direction == 'backlinks' or link['status'] == 'resolved' else 'Enlace sin destino único')
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
                    self.outgoing_buttons.append(button)
        disk = data.get('disk_state')
        if disk and disk['state'] != 'current':
            if disk['state'] == 'metadata_only':
                message = 'Metadatos actualizados; contenido idéntico (SHA-256 verificado)'
            elif disk['state'] == 'modified':
                message = 'Archivo modificado en disco; reindexa para actualizar los enlaces'
            else:
                message = 'Estado del archivo en disco: ' + disk['state']
            self.metadata_label.set_text(self.metadata_label.get_text() + '\n' + message)
            self.health_box.append(label(message, css='muted' if disk['state'] == 'metadata_only' else 'warning'))
        health = data['health']
        for error in health['errors']:
            self.health_box.append(label(f"{error['path']}: {error['error']}", css='warning'))
        for conflict in health['conflicts']:
            self.health_box.append(label(f"Conflicto: {conflict['old_path']} → {', '.join(conflict['candidates'])}", css='ambiguous'))
        if not health['errors'] and not health['conflicts']:
            self.health_box.append(label('Sin errores de indexación ni conflictos para esta nota.'))

    def on_close(self, *_):
        if self.creation_dialog is not None:
            self.creation_dialog.destroy()
            self.creation_dialog = None
        self.closed = True
        self.jobs.clear()
        if self.debounce:
            GLib.source_remove(self.debounce)
            self.debounce = None
        self.executor.shutdown(wait=False, cancel_futures=True)
        return False


def run(workspace, query='', select=None, *, smoke_test=False, page_size=50, link_page_size=50, editor=None, editor_dry_run=False, health_filter=None):
    if not available():
        raise RuntimeError('GTK 4 no tiene un display disponible; usa --backend snapshot o Xvfb')
    app = Gtk.Application(application_id='io.trama.Reader', flags=Gio.ApplicationFlags.NON_UNIQUE)
    result = dict(report=None, error=None)
    def activate(application):
        window = Window(application, workspace, query, select, page_size=page_size, link_page_size=link_page_size, editor=editor, editor_dry_run=editor_dry_run, health_filter=health_filter)
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
                if state['health_view'] and not state['health_response']['ok']:
                    raise RuntimeError('La cola de salud no está disponible')
                rows = state['health_response']['data']['items'] if state['health_view'] else state['search']['data']['results']
                documents = [r['source'] for r in rows] if state['health_view'] else rows
                if not selected_from_widget:
                    chosen = next((i for i, row in enumerate(documents) if select in (row['uuid'], row['rel_path'])), 0)
                    if rows and (not select or select in (documents[chosen]['uuid'], documents[chosen]['rel_path'])):
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
                assert [w.get_text() for w in window.result_labels] == ([issue_caption(r) for r in rows] if state['health_view'] else [d['title'] for d in rows]), 'Resultados no renderizados'
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
