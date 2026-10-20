"""Vista terminal sin curses ni dependencias gráficas."""
import json
import sys

from . import Presenter, link_text, notices, status_text, page_text


def plain(text):
    return ''.join(c if c in '\n\t' or c.isprintable() else repr(c)[1:-1] for c in str(text))


def render(snapshot):
    lines = ['Trama · solo lectura', status_text(snapshot['status']), *notices(snapshot)]
    search = snapshot['search']
    if search and search['ok']:
        lines.append(f"Búsqueda: {snapshot['query']} · {page_text(snapshot)}")
        for n, row in enumerate(search['data']['results']):
            lines.append(f"  {n}: {row['title']} · {row['rel_path']} · {row['uuid']}\n{row['snippet']}")
    inspect = snapshot['inspection']
    if inspect and inspect['ok']:
        data = inspect['data']
        doc = data['document']
        if doc:
            lines += [f"Nota: {doc['title']}", f"{doc['rel_path']} · {doc['uuid']} · {doc['identity_origin']}"]
        for section in ('backlinks', 'outgoing_links'):
            lines.append('Backlinks' if section == 'backlinks' else 'Enlaces salientes')
            lines.extend(f"  {n}: {link_text(link, section)}" for n, link in enumerate(data[section]))
        lines += [f"Aviso: {error['path']}: {error['error']}" for error in data['health']['errors']]
        lines += [f"Conflicto: {c['old_path']} → {', '.join(c['candidates'])}" for c in data['health']['conflicts']]
    return plain('\n'.join(lines))


def run(workspace, query='', select=None, *, snapshot=False, page_size=50):
    controller = Presenter(workspace, page_size=page_size)
    controller.refresh(query=query, select=select)
    if snapshot:
        print(json.dumps(controller.snapshot(), ensure_ascii=False, indent=2))
        return 0 if all(r is None or r['ok'] for r in (controller.state[k] for k in ('status', 'search', 'inspection'))) else 1
    print(render(controller.snapshot()))
    if not sys.stdin.isatty():
        return 0 if all(r is None or r['ok'] for r in (controller.state[k] for k in ('status', 'search', 'inspection'))) else 1
    print('/buscar TEXTO · /abrir UUID|RUTA · /resultado N · /entrada N · /salida N · /atras · /siguiente · /anterior · /abajo · /arriba · /foco PANEL · /tab · /shift-tab · /enlace-abajo · /enlace-arriba · /enter · /escape · /estado · /salir')
    while True:
        try:
            text = input('trama> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        command, _, argument = text.partition(' ')
        try:
            if command == '/salir':
                break
            elif command == '/buscar':
                controller.search(argument)
            elif command == '/abrir':
                controller.select(argument)
            elif command == '/resultado':
                response = controller.state['search']
                if response and response['ok']:
                    position = int(argument)
                    if not 0 <= position < len(response['data']['results']):
                        raise ValueError('Resultado fuera de rango')
                    controller.select_result(position)
            elif command in ('/entrada', '/salida'):
                controller.navigate('backlinks' if command == '/entrada' else 'outgoing_links', int(argument))
            elif command in ('/siguiente', '/anterior'):
                controller.change_page(1 if command == '/siguiente' else -1)
            elif command in ('/abajo', '/arriba'):
                controller.move_result(1 if command == '/abajo' else -1)
            elif command == '/foco':
                controller.set_focus(argument)
            elif command in ('/tab', '/shift-tab'):
                controller.cycle_focus(command == '/shift-tab')
            elif command in ('/enlace-abajo', '/enlace-arriba'):
                controller.move_link(controller.state['focus'], 1 if command == '/enlace-abajo' else -1)
            elif command == '/enter':
                controller.activate()
            elif command == '/escape':
                controller.escape()
                if controller.state['close_requested']:
                    break
            elif command == '/atras':
                controller.back()
            elif command == '/estado':
                controller.refresh()
            else:
                print('Comando no reconocido')
                continue
        except (ValueError, IndexError):
            print('Selección inválida')
        print(render(controller.snapshot()))
    return 0
