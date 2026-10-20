"""Presentador de solo lectura compartido por GTK y terminal."""
import copy

from .. import ui_contract


FOCUS_ORDER = ('search', 'results', 'backlinks', 'outgoing_links', 'health', 'navigation')


class Presenter:
    """Uso secuencial: GTK lo llama desde un único worker, nunca desde el main loop."""
    def __init__(self, workspace, contract=ui_contract, *, page_size=50):
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("page_size debe estar entre 1 y 100")
        self.workspace = workspace
        self.contract = contract
        self.state = dict(ui_version=1, query='', selected_uuid=None, history=[],
                          status=None, search=None, inspection=None, notice='', page_size=page_size, offset=0,
                          result_cursor=-1, link_cursors={'backlinks': -1, 'outgoing_links': -1},
                          focus='search', close_requested=False)

    def snapshot(self):
        return copy.deepcopy(self.state)

    def refresh_status(self):
        self.state['status'] = self.contract.status(self.workspace)

    def search(self, text, *, offset=0):
        self.state['query'] = text
        self.state['offset'] = offset
        self.state['search'] = self.contract.search(self.workspace, text, limit=self.state['page_size'], offset=offset)
        self.state['notice'] = ''
        self.state['result_cursor'] = next((i for i, row in enumerate(self.results())
                                            if row['uuid'] == self.state['selected_uuid']), -1)

    def results(self):
        response = self.state['search']
        return response['data']['results'] if response and response['ok'] else []

    def select_result(self, position):
        rows = self.results()
        if type(position) is not int or not 0 <= position < len(rows):
            return False
        self.state['focus'] = 'results'
        return self.select(rows[position]['uuid'])

    def move_result(self, delta):
        rows = self.results()
        if not rows or type(delta) is not int or delta == 0:
            return False
        cursor = self.state['result_cursor']
        if cursor < 0:
            cursor = -1 if delta >= 0 else len(rows)
        total = self.state['search']['data']['total']
        absolute = max(0, min(total - 1, self.state['offset'] + cursor + delta))
        page = min(10000, (absolute // self.state['page_size']) * self.state['page_size'])
        if page != self.state['offset']:
            self.search(self.state['query'], offset=page)
        return self.select_result(min(absolute - page, len(self.results()) - 1))

    def change_page(self, direction):
        response = self.state['search']
        if not response or not response['ok'] or direction not in (-1, 1):
            return False
        offset = response['data']['next_offset'] if direction == 1 else max(0, self.state['offset'] - self.state['page_size'])
        if offset is None or offset == self.state['offset'] or offset > 10000:
            return False
        self.search(self.state['query'], offset=offset)
        return self.select_result(0)

    def set_focus(self, group):
        if group not in FOCUS_ORDER:
            raise ValueError('Panel de foco desconocido')
        self.state['focus'] = group
        if group in self.state['link_cursors'] and self.state['link_cursors'][group] < 0:
            response = self.state['inspection']
            if response and response['ok'] and response['data'][group]:
                self.state['link_cursors'][group] = 0

    def cycle_focus(self, reverse=False):
        index = FOCUS_ORDER.index(self.state['focus'])
        self.set_focus(FOCUS_ORDER[(index + (-1 if reverse else 1)) % len(FOCUS_ORDER)])

    def move_link(self, direction, delta):
        response = self.state['inspection']
        if direction not in self.state['link_cursors'] or not response or not response['ok']:
            return False
        links = response['data'][direction]
        if not links:
            return False
        cursor = self.state['link_cursors'][direction]
        if cursor < 0:
            cursor = -1 if delta >= 0 else len(links)
        self.state['link_cursors'][direction] = max(0, min(len(links) - 1, cursor + delta))
        self.set_focus(direction)
        return True

    def activate(self, group=None):
        group = group or self.state['focus']
        if group == 'results':
            return self.select_result(max(0, self.state['result_cursor']))
        if group in self.state['link_cursors']:
            return self.navigate(group, max(0, self.state['link_cursors'][group]))
        return False

    def escape(self, *, text=None, focus=None):
        self.state['close_requested'] = False
        if (self.state['query'] if text is None else text):
            self.search('')
            self.set_focus('search')
        elif (focus or self.state['focus']) != 'search':
            self.set_focus('search')
        else:
            self.state['close_requested'] = True

    def select(self, document, *, remember=True):
        response = self.contract.inspect_document(self.workspace, document)
        self.state['inspection'] = response
        self.state['notice'] = ''
        if response['ok'] and response['data']['document'] is not None:
            identity = response['data']['document']['uuid']
            current = self.state['selected_uuid']
            if remember and current and current != identity:
                self.state['history'].append(current)
                del self.state['history'][:-100]
            self.state['selected_uuid'] = identity
            self.state['result_cursor'] = next((i for i, row in enumerate(self.results()) if row['uuid'] == identity), -1)
            if current != identity:
                self.state['link_cursors'] = {'backlinks': -1, 'outgoing_links': -1}
            return True
        return False

    def back(self):
        if not self.state['history']:
            return False
        if self.select(self.state['history'][-1], remember=False):
            self.state['history'].pop()
            return True
        return False

    def navigate(self, direction, position):
        response = self.state['inspection']
        if direction not in ('backlinks', 'outgoing_links') or not response or not response['ok']:
            self.state['notice'] = 'No hay un enlace navegable seleccionado'
            return False
        links = response['data'][direction]
        if type(position) is not int or not 0 <= position < len(links):
            self.state['notice'] = 'Enlace no disponible'
            return False
        self.set_focus(direction)
        self.state['link_cursors'][direction] = position
        link = links[position]
        if direction == 'backlinks':
            return self.select(link['source']['uuid'])
        if link['status'] == 'resolved' and link['target'] is not None:
            return self.select(link['target']['uuid'])
        self.state['notice'] = 'El enlace no tiene un destino único; no se abre automáticamente'
        return False

    def refresh(self, query=None, select=None, *, auto_select=False):
        self.refresh_status()
        self.search(self.state['query'] if query is None else query, offset=self.state['offset'] if query is None else 0)
        document = select or self.state['selected_uuid']
        if not document and auto_select and self.state['search']['ok']:
            results = self.state['search']['data']['results']
            document = results[0]['uuid'] if results else None
        if document:
            self.select(document, remember=False)
        return self.snapshot()


def status_text(response):
    if not response:
        return 'Cargando estado…'
    if not response['ok']:
        return f"{response['state']}: {response['error']['message']}"
    c = response['data']['counts']
    return (f"{c['notes']} notas · {c['links']} enlaces · {c['broken']} rotos · "
            f"{c['ambiguous']} ambiguos · {c['needs_update']} por actualizar · "
            f"{c['conflicts']} conflictos · {c['errors']} errores")


def link_text(link, direction):
    peer = link['source'] if direction == 'backlinks' else link['target']
    name = peer['title'] if peer else link['raw']
    badge = ' · Actualizar enlace' if link['needs_update'] else ''
    return f"{name} · {link['status']}{badge}\nLínea {link['line']}: {link['context']}"


def notices(snapshot):
    result = []
    for field in ('status', 'search', 'inspection'):
        response = snapshot[field]
        if response and not response['ok']:
            text = f"{response['state']}: {response['error']['message']}"
            if text not in result:
                result.append(text)
    if snapshot['notice']:
        result.append(snapshot['notice'])
    return result


def page_text(snapshot):
    response = snapshot['search']
    if not response or not response['ok']:
        return 'Búsqueda no disponible'
    data = response['data']
    first = data['offset'] + 1 if data['results'] else 0
    last = data['offset'] + len(data['results']) if data['results'] else 0
    return f"Mostrando {first}–{last} de {data['total']} resultados"
