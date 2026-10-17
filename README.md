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
espacio. Todos los comandos requieren directorio explícito. Index solo escribe
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

Los renombres importados se reconocen automáticamente solo con evidencia unívoca
(hash, tamaño, dispositivo e inode; ruta anterior desaparecida). No se fusionan copias.
Para confirmar un traslado con edición o entre sistemas de archivos, antes de indexar
la ruta nueva, usa el UUID registrado y su nueva ruta relativa:

```bash
PYTHONPATH=src .venv/bin/python -m trama_core index .demo/espacio --relocate UUID RUTA_NUEVA
```

Este comando solo actualiza estado; no mueve ni modifica documentos. `--assign-ids`
se ha eliminado. El grafo v3 expone `needs_update` y `identity_conflicts`.

Los enlaces previamente resueltos conservan destino por UUID si su ruta o título
ya no resuelve. Los IDs duplicados se reportan en errors; no se fusionan documentos.


Inspeccionar y resolver después de indexar:

```bash
PYTHONPATH=src .venv/bin/python -m trama_core conflicts .demo/espacio --json
PYTHONPATH=src .venv/bin/python -m trama_core resolve .demo/espacio OLD_UUID RUTA_ACTUAL --preview
PYTHONPATH=src .venv/bin/python -m trama_core resolve .demo/espacio OLD_UUID RUTA_ACTUAL --apply
```

Ejemplo completo con datos nuevos, vista previa, aplicación y verificación de bytes:
`.venv/bin/python docs/demo-resolution.py`. Crea `.demo/espacio/incremento3`;
si ya existe, se detiene para preservar sus archivos. Nunca modifica notas existentes.
Consultar docs/data-format.md para recuperación y límite de una operación por espacio.
