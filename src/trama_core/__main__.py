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
            p.add_argument("--assign-ids", action="store_true", help="Añadir UUIDv4 a Markdown sin id")
        if name == "search":
            p.add_argument("text")
        if name == "backlinks":
            p.add_argument("target", help="Ruta relativa exacta o UUID")
    args = parser.parse_args()
    try:
        result = index(args.workspace, assign_ids=args.assign_ids) if args.command == "index" else query(
            args.workspace, args.command, getattr(args, "text", getattr(args, "target", None)))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"trama: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
