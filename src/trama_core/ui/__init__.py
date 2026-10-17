"""Presentador de solo lectura compartido por GTK y terminal."""
import copy

from .. import ui_contract


class Presenter:
    """Uso secuencial: GTK lo llama desde un único worker, nunca desde el main loop."""
    def __init__(self, workspace, contract=ui_contract):
        self.workspace = workspace
        self.contract = contract
        self.state = dict(ui_version=1, query='', selected_uuid=None, history=[],
                          status=None, search=None, inspection=None, notice='')

    def snapshot(self):
        return copy.deepcopy(self.state)

    def refresh_status(self):
        self.state['status'] = self.contract.status(self.workspace)

    def search(self, text):
        self.state['query'] = text
        self.state['search'] = self.contract.search(self.workspace, text)
        self.state['notice'] = ''

    def select(self, document, *, remember=True):
        response = self.contract.inspect_document(self.workspace, document)
        self.state['inspection'] = response
        self.state['notice'] = ''
        if response['ok'] and response['data']['document'] is not None:
            identity = response['data']['document']['uuid']
            current = self.state['selected_uuid']
            if remember and current and current != identity:
                self.state['history'].append(current)
            self.state['selected_uuid'] = identity
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
        link = links[position]
        if direction == 'backlinks':
            return self.select(link['source']['uuid'])
        if link['status'] == 'resolved' and link['target'] is not None:
            return self.select(link['target']['uuid'])
        self.state['notice'] = 'El enlace no tiene un destino único; no se abre automáticamente'
        return False

    def refresh(self, query=None, select=None, *, auto_select=False):
        self.refresh_status()
        self.search(self.state['query'] if query is None else query)
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
