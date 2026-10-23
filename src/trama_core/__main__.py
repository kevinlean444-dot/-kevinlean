import argparse
import json
import sqlite3
import sys

from .core import index, query
from .reconciliation import conflicts, resolve
from . import ui_contract


def main():
    parser = argparse.ArgumentParser(description="Índice local de Trama")
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser('new', help='Crear exclusivamente una nota nativa e indexarla')
    new.add_argument('workspace')
    new.add_argument('name', help='Título o ruta relativa .md; padres existentes')
    new.add_argument('--open', action='store_true', dest='open_editor')
    new.add_argument('--editor')
    new.add_argument('--editor-dry-run', action='store_true')
    for name in ("index", "search", "backlinks", "graph", "conflicts", "resolve"):
        p = sub.add_parser(name)
        p.add_argument("workspace", help="Directorio explícito del espacio")
        if name == "conflicts":
            p.add_argument("--json", action="store_true")
        if name == "resolve":
            p.add_argument("old_uuid")
            p.add_argument("destination", help="UUID actual o ruta relativa indexada")
            mode = p.add_mutually_exclusive_group()
            mode.add_argument("--preview", "--dry-run", action="store_true")
            mode.add_argument("--apply", action="store_true")
        if name == "index":
            p.add_argument("--relocate", nargs=2, metavar=("UUID", "RUTA"), help="Confirmar traslado de nota importada antes de indexar la nueva ruta")
        if name == "search":
            p.add_argument("text")
        if name == "backlinks":
            p.add_argument("target", help="Ruta relativa exacta o UUID")
    view = sub.add_parser("ui-query", help="Contrato de lectura JSON v1")
    view.add_argument("workspace")
    modes = view.add_subparsers(dest="view", required=True)
    search_view = modes.add_parser("search")
    search_view.add_argument("text")
    search_view.add_argument("--limit", type=int, default=20)
    search_view.add_argument("--offset", type=int, default=0)
    inspect_view = modes.add_parser("inspect")
    inspect_view.add_argument("document")
    inspect_view.add_argument("--link-limit", type=int, default=50)
    inspect_view.add_argument("--backlinks-offset", type=int, default=0)
    inspect_view.add_argument("--outgoing-offset", type=int, default=0)
    modes.add_parser("status")
    ui = sub.add_parser("ui", help="Ventana GTK 4 o terminal; creación nativa explícita")
    ui.add_argument("workspace")
    ui.add_argument("--backend", choices=("auto", "gtk", "tui", "snapshot"), default="auto")
    ui.add_argument("--query", default="")
    ui.add_argument("--select")
    ui.add_argument("--page-size", type=int, default=50, help="Resultados por página, 1..100")
    ui.add_argument("--link-page-size", type=int, default=50)
    ui.add_argument("--editor", help="Comando externo, sin expansión de shell")
    ui.add_argument("--editor-dry-run", action="store_true")
    ui.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == 'new':
            from .notes import create_note
            from .desktop_actions import open_document
            result = create_note(args.workspace, args.name)
            if result['ok'] and args.open_editor:
                result['external_action'] = open_document(args.workspace, result['uuid'], command=args.editor, dry_run=args.editor_dry_run)
                result['ok'] = result['external_action']['ok']
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result['ok'] else 1
        if args.command == "ui":
            from .ui.launcher import run
            return run(args.workspace, backend=args.backend, query=args.query, select=args.select, smoke_test=args.smoke_test, page_size=args.page_size, link_page_size=args.link_page_size, editor=args.editor, editor_dry_run=args.editor_dry_run)
        if args.command == "ui-query":
            if args.view == "search":
                result = ui_contract.search(args.workspace, args.text, limit=args.limit, offset=args.offset)
            elif args.view == "inspect":
                result = ui_contract.inspect_document(args.workspace, args.document, link_limit=args.link_limit, backlinks_offset=args.backlinks_offset, outgoing_offset=args.outgoing_offset)
            else:
                result = ui_contract.status(args.workspace)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result['ok'] else 1
        if args.command == "resolve":
            result = resolve(args.workspace, args.old_uuid, args.destination, apply=args.apply)
        elif args.command == "conflicts":
            result = conflicts(args.workspace)
            if not args.json:
                for row in result['orphans']:
                    print(f"{row['id']} · {row['old_path']} · hash={row['content_hash']} · conflictos={len(row['pending_conflicts'])} · referencias históricas={row['historical_references']} · backlinks={row['indexed_backlinks']}")
                    for candidate in row['candidates']:
                        print(f"  {candidate['id']} · {candidate['rel_path']} · hash={candidate['content_hash']} · hash coincidente={candidate['hash_match']} · candidata registrada={candidate['recorded_candidate']}")
                if not result['orphans']:
                    print("Sin identidades históricas pendientes")
                return 0
        else:
            result = index(args.workspace, relocate=args.relocate) if args.command == "index" else query(
                args.workspace, args.command, getattr(args, "text", getattr(args, "target", None)))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"trama: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
