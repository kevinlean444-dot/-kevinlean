import argparse
import json
import sqlite3
import sys

from .core import index, query


def main():
    parser = argparse.ArgumentParser(description="Índice local de Trama")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("index", "search", "backlinks", "graph"):
        p = sub.add_parser(name)
        p.add_argument("workspace", help="Directorio explícito del espacio")
        if name == "index":
            p.add_argument("--relocate", nargs=2, metavar=("UUID", "RUTA"), help="Confirmar traslado de nota importada antes de indexar la nueva ruta")
        if name == "search":
            p.add_argument("text")
        if name == "backlinks":
            p.add_argument("target", help="Ruta relativa exacta o UUID")
    args = parser.parse_args()
    try:
        result = index(args.workspace, relocate=args.relocate) if args.command == "index" else query(
            args.workspace, args.command, getattr(args, "text", getattr(args, "target", None)))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"trama: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
