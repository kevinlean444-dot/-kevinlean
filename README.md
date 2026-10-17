# Trama · núcleo 0.1

Prototipo local sin GUI ni privilegios. Python >=3.11 con sqlite3/FTS5.
La biblioteca estándar basta; no se necesita instalar el paquete para usar la CLI.

Desde la raíz del repositorio, en Linux:

```bash
python3 -m venv .venv
.venv/bin/python -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(body)')"
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
mkdir -p .demo
cp -R fixtures .demo/espacio
PYTHONPATH=src .venv/bin/python -m trama_core index .demo/espacio
PYTHONPATH=src .venv/bin/python -m trama_core search .demo/espacio cafe
PYTHONPATH=src .venv/bin/python -m trama_core backlinks .demo/espacio 'Ideas de estudio.md'
PYTHONPATH=src .venv/bin/python -m trama_core graph .demo/espacio
```

La copia del ejemplo debe hacerse una sola vez; para repetir basta reindexar el mismo
espacio. Todos los comandos requieren directorio explícito. Sin --assign-ids, index solo escribe
`.trama/manifest.json` e `index.sqlite` dentro de ese directorio (y temporales de estado).
Los errores por archivo aparecen en JSON, también en graph; revisar aunque index
termine con éxito. Errores globales devuelven código 1.

Entorno observado: Python 3.12.14, SQLite 3.53.1 con FTS5. No se requieren Arch ni Xfce.
Si venv o FTS5 faltan, detenerse e identificar el proveedor de Python del entorno;
no instalar paquetes del sistema a ciegas. El proyecto no descarga dependencias.
El backend setuptools del pyproject solo se necesita para empaquetar, no para este
recorrido por PYTHONPATH.

Consulta [arquitectura](docs/architecture.md) y [formato](docs/data-format.md).
El manifiesto conserva identidad; el índice permite búsqueda; las relaciones explícitas
forman el grafo. Los traslados conservan identidad si hay UUID embebido. Consulta docs/data-format.md.

Para preparar notas Markdown antes de moverlas (modifica solo las que no tienen ID):

```bash
PYTHONPATH=src .venv/bin/python -m trama_core index .demo/espacio --assign-ids
```

Los enlaces previamente resueltos conservan destino por UUID si su ruta o título
ya no resuelve. Los IDs duplicados se reportan en errors; no se fusionan documentos.
