"""Vista terminal sin curses ni dependencias gráficas."""
import json
import sys

from . import Presenter, link_text, notices, status_text


def plain(text):
    return ''.join(c if c in '\n\t' or c.isprintable() else repr(c)[1:-1] for c in str(text))


def render(snapshot):
    lines = ['Trama · solo lectura', status_text(snapshot['status']), *notices(snapshot)]
    search = snapshot['search']
    if search and search['ok']:
        lines.append(f"Búsqueda: {snapshot['query']} · {search['data']['total']} resultados")
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


def run(workspace, query='', select=None, *, snapshot=False):
    controller = Presenter(workspace)
    controller.refresh(query=query, select=select)
    if snapshot:
        print(json.dumps(controller.snapshot(), ensure_ascii=False, indent=2))
        return 0 if all(r is None or r['ok'] for r in (controller.state[k] for k in ('status', 'search', 'inspection'))) else 1
    print(render(controller.snapshot()))
    if not sys.stdin.isatty():
        return 0 if all(r is None or r['ok'] for r in (controller.state[k] for k in ('status', 'search', 'inspection'))) else 1
    print('/buscar TEXTO · /abrir UUID|RUTA · /resultado N · /entrada N · /salida N · /atras · /estado · /salir')
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
                    controller.select(response['data']['results'][position]['uuid'])
            elif command in ('/entrada', '/salida'):
                controller.navigate('backlinks' if command == '/entrada' else 'outgoing_links', int(argument))
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
