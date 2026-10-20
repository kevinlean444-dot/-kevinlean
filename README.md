# Trama · núcleo 0.1

Prototipo local con CLI, TUI y ventana GTK 4 opcional de solo lectura.
El núcleo usa Python >=3.11 con sqlite3/FTS5 y no requiere privilegios.
La biblioteca estándar basta; no se necesita instalar el paquete para usar la CLI.

Desde la raíz del repositorio, en Linux. Crear .venv solo si no existe; para GTK
seguir primero docs/ui-window.md y usar el Python de la distribución:

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

Entorno inicial del núcleo: Python 3.12.14, SQLite 3.53.1 con FTS5.
Entorno gráfico verificado: Python 3.13.5, SQLite 3.46.1, GTK 4.18.6 y PyGObject 3.50.0. No se requieren Arch ni Xfce.
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
Consultar docs/data-format.md para recuperación y protocolo de bloqueo por espacio.


Lectura para frontends, JSON v1, sin GTK:

```bash
PYTHONPATH=src .venv/bin/python -m trama_core index .demo/espacio
PYTHONPATH=src .venv/bin/python -m trama_core ui-query .demo/espacio search cafe --limit 20
PYTHONPATH=src .venv/bin/python -m trama_core ui-query .demo/espacio inspect 'Ideas de estudio.md'
PYTHONPATH=src .venv/bin/python -m trama_core ui-query .demo/espacio status
```

Ver [contrato UI](docs/ui-contract.md). Los escritores toman flock exclusivo sin
esperar; los lectores, compartido. La UI devuelve busy o recovery_needed de forma
estructurada. El índice se actualiza a esquema 4 al reindexar; no lee documentos
originales para servir fichas ni resultados.


Ventana GTK 4 de solo lectura y alternativa de terminal (incremento 5):

```bash
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend gtk --query cafe --select Inicio.md
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend snapshot --query cafe --select Inicio.md
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend tui --query cafe
```

La ventana tiene búsqueda, inspector, backlinks navegables, Atrás y barra de estado
con paleta beige/café. No escribe notas ni indexa automáticamente. GTK requiere
PyGObject compatible con el Python del venv; terminal/snapshot no lo necesitan.
Ver [dependencias Debian/Arch y prueba GTK real](docs/ui-window.md). En el contenedor
actual se preparó Python 3.13.5 con GTK 4.18.6 local; el núcleo también conserva sus
pruebas anteriores. Para la suite completa sin pantalla física:

```bash
. scripts/gtk-env.sh
xvfb-run -a dbus-run-session -- env GTK_A11Y=none GSK_RENDERER=cairo G_DEBUG=fatal-warnings PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```


Ergonomía de escritorio (incremento 6):

```bash
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend gtk --query cafe --page-size 50
```

Ctrl+F o / fuera de edición enfoca la búsqueda; flechas seleccionan resultados,
Tab/Shift+Tab recorren paneles, Enter abre un enlace y Alt+Izquierda vuelve. AvPág y
RePág cambian de página desde resultados. Escape limpia y, en búsqueda vacía, cierra.
La lista muestra el rango de resultados, máximo 50 por defecto (configurable 1..100).
[Tabla completa de atajos y límites](docs/ui-window.md). Snapshot y TUI aceptan
--page-size; el controlador conserva cursores e historial limitado sin escribir notas.


Inspector paginado y acciones de escritorio (incremento 7):

```bash
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend gtk --query cafe --link-page-size 50 --editor-dry-run
```

AvPág/RePág en backlinks o salientes cambia su página. Ctrl+R/F5 recarga, Ctrl+Shift+R
reindexa explícitamente con bloqueo y Ctrl+O abre el documento en editor externo
(o muestra la orden si --editor-dry-run). El inspector avisa si el archivo cambió
por metadatos y aún no se reindexó. [Acciones, seguridad y límites](docs/ui-window.md).
