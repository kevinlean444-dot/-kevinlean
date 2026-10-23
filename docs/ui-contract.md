# Contrato de lectura de Trama · versión 1

API Python en `trama_core.ui_contract`, solo biblioteca estándar. El frontend no
abre SQLite ni altera notas. El inspector consulta metadatos de disco y verifica SHA-256 si difieren;
el texto mostrado y los enlaces siguen procediendo del índice. Todas las
respuestas son objetos JSON; los nombres de campos siguientes forman el contrato.
Versión de contrato 1, manifiesto 2, esquema SQLite 4 y grafo heredado 3 son números
independientes. Campos nuevos incompatibles requerirán otra versión del contrato.

## API y CLI

```python
from trama_core import ui_contract
ui_contract.search(space, 'cafe', limit=20, offset=0)
ui_contract.inspect_document(space, 'nota.md', link_limit=50, backlinks_offset=0, outgoing_offset=0)  # también UUID
ui_contract.status(space)
```

```bash
PYTHONPATH=src .venv/bin/python -m trama_core index .demo/espacio
PYTHONPATH=src .venv/bin/python -m trama_core ui-query .demo/espacio search cafe --limit 20 --offset 0
PYTHONPATH=src .venv/bin/python -m trama_core ui-query .demo/espacio inspect 'Ideas de estudio.md'
PYTHONPATH=src .venv/bin/python -m trama_core ui-query .demo/espacio status
```

`ui-query` escribe una sola respuesta JSON UTF-8 en stdout. Código 0 en éxito y 1
para errores del contrato (stderr vacío). Los errores sintácticos de argparse siguen
el código 2 y su ayuda habitual en stderr. Las funciones Python devuelven el mismo
objeto sin imprimir. No hay promesas de latencia: no se hizo un benchmark.

## Envoltura común exacta

```json
{
  "version": 1,
  "operation": "status",
  "ok": true,
  "state": "ready",
  "data": {},
  "error": null
}
```

- `version`: entero 1. `operation`: `search`, `inspect` o `status`.
- `ok`: booleano. `state`: `ready` o uno de los códigos de error de la tabla.
- Éxito: `data` contiene el payload de la operación y `error` es null.
- Error: `data` es null; `error` tiene exactamente `code`, `message`, `action`,
  tres strings. `code` coincide con `state`. El frontend decide por code/action;
  message es texto humano en español, no una clave para lógica de aplicación.

| code/state | significado | action |
| --- | --- | --- |
| busy | otro escritor tiene EX, o no se pudo tomar el bloqueo | retry |
| recovery_needed | hay publicación pending; lectura UI no la completa | index |
| index_missing | falta SQLite o el directorio de metadatos | index |
| manifest_missing | hay índice pero falta su manifiesto | restore_manifest |
| manifest_invalid | JSON/formato de manifiesto incompatible | restore_manifest |
| index_stale | esquema anterior a 4 o huella distinta del manifiesto | index |
| index_invalid | SQLite corrupto, esquema incompleto o consulta inválida | index |
| not_found | UUID/ruta no registrado y sin error de indexación asociado | choose_document |
| document_ambiguous | varias identidades históricas para esa ruta | choose_document |
| invalid_request | argumentos fuera de los límites de esta API | fix_request |
| workspace_invalid | ruta o metadatos inseguros, incluido symlink de .lock | inspect_workspace |
| io_error | permisos u otro error del sistema al leer metadatos | inspect_workspace |

Las acciones son sugerencias para el controlador, nunca instrucciones ejecutadas
automáticamente por este módulo. Restaurar un manifiesto requiere copia fiable:
no regenerarlo sin advertir que contiene identidad y referencias históricas.

## Tipo Document exacto

Se usa en la ficha y en cada resultado de búsqueda:

| campo | tipo / significado |
| --- | --- |
| uuid | string UUID canónico |
| title | string, título indexado o nombre sin extensión |
| rel_path | string, ruta relativa con `/` |
| kind | `note` o `attachment` |
| content_hash | string SHA-256 o null para histórico antiguo sin observación |
| identity_origin | `frontmatter` o `manifest` según última indexación |
| identity_source | alias de identity_origin, añadido en incremento 8 |
| deleted | booleano del manifiesto |
| indexed | booleano: documento activo presente en SQLite |
| backlink_count | entero: documentos fuente distintos que tienen enlaces resueltos entrantes |
| has_conflicts | booleano: participa como histórico o candidata por ruta actual/previa |
| needs_update_count | entero: ocurrencias entrantes o salientes con needs_update; autoenlace cuenta una vez |

Un registro ilegible que antes se indexó sigue siendo inspeccionable por UUID/ruta,
con `indexed=false` y sus errores. Un UUID histórico eliminado también se puede
inspeccionar, con `deleted=true`. No se devuelve el texto completo de la nota.

## Búsqueda: data

Campos exactos: `query` string original, `limit` entero, `offset` entero, `total`
entero, `next_offset` entero o null, `results` array. Cada resultado contiene todos
los campos Document y, además, `snippet` string y `relevance` número real finito.

Consulta por frase literal, sin operadores FTS aportados por el usuario. Texto máximo
500 caracteres; limit 1..100 (20 por defecto); offset 0..10000 (0 por defecto).
Texto vacío o solo espacios da cero resultados. No es búsqueda por prefijo ni fuzzy.
Busca solo notas activas. FTS5 unicode61 remove_diacritics=2 permite cafe→café y no
promete equivalencia universal de todos los alfabetos. Orden por bm25 ascendente
(menor es más relevante), después rel_path y UUID para resolver empates. La relevancia
solo se compara dentro de una respuesta, no entre diferentes consultas/índices.

El snippet usa FTS5 con hasta 24 tokens y marca coincidencias con `[` y `]`, separando
omisiones por ` … `. Es texto plano que puede contener caracteres de Markdown/HTML;
GTK debe presentarlo como texto sin interpretar markup ni ejecutar vínculos. La
paginación es de offset sobre el estado actual; indexar entre páginas puede cambiar
orden o total. next_offset es null al agotar resultados. No se mantiene un snapshot
entre llamadas distintas.

## Inspector: data

Campos exactos:

- `link_pages`: metadatos de paginación independientes de backlinks y outgoing_links.
- `disk_state`: estado de metadatos del archivo seleccionado, o null si no hay documento.
- `document`: objeto Document o null.
- `backlinks`: array Link de ocurrencias cuyo destino resuelto es el UUID consultado.
- `outgoing_links`: array Link de todas las ocurrencias con ese UUID como fuente.
- `health`: objeto con `errors`, `conflicts` y `historical_reference_count`.

Al resolver una ruta se prefiere su registro activo; si solo hay varios históricos,
se requiere UUID. Si una ruta falló antes de obtener identidad, la ficha devuelve
`document=null`, arrays de enlaces vacíos, páginas con total=0, disk_state=null y errores en health.

Link tiene exactamente:

| campo | tipo / significado |
| --- | --- |
| position | entero, posición global desde 0 en esta generación del índice; no es ID permanente |
| source | `{uuid, title, rel_path}` del documento fuente |
| target | `{uuid, title, rel_path}` del destino resuelto o null |
| raw | string original del destino del enlace |
| status | resolved, unresolved, ambiguous, external, outside o invalid |
| candidate_uuids | array de strings, vacío si no hay candidatas |
| needs_update | booleano; destino mantenido por binding histórico |
| line | entero desde 1, línea de inicio del enlace en la fuente al indexarla |
| context | string de esa línea alrededor de la coincidencia; hasta 500 caracteres |

Orden de enlaces: position ascendente. Las ocurrencias repetidas se conservan; dos
enlaces de la misma nota no incrementan backlink_count dos veces. El contexto se
limita a unos 160 caracteres a cada lado del enlace y luego a 500 caracteres; una
línea muy larga puede truncarse. Línea/contexto corresponden al último index, nunca
se recalculan leyendo el contenido desde el contrato. Un disk_state=modified advierte
que esas posiciones pueden estar desactualizadas. Las limitaciones del parser
Markdown del núcleo se conservan (no es CommonMark completo).

`health.errors`: array `{path, error}` de errores de indexación cuya ruta coincide
con la actual o una previa; orden path/error. `health.conflicts`: array de conflictos
pendientes donde participa el documento, orden id/old_path. Cada conflicto es
`{id, old_path, candidates}`; candidates son rutas, no IDs. Las resoluciones archivadas
no son conflictos pendientes. `historical_reference_count`: número de bindings del
manifiesto que aún apuntan al UUID, incluso sin destino activo; no equivale al número
de documentos fuente distintos ni a la cantidad de backlinks resueltos.

## Estado global: data

Campos exactos: `counts`, `conflicts`, `errors`. Los dos arrays usan las formas y
orden anteriores (todos los conflictos y errores del espacio). counts contiene solo
enteros no negativos:

- notes, attachments: documentos activos indexados de cada tipo.
- links: todas las ocurrencias indexadas, incluidos externos, rotos y repetidos.
- broken: solo status=unresolved. ambiguous se cuenta aparte.
- ambiguous, external, outside, invalid: ocurrencias de cada estado.
- needs_update: ocurrencias históricas marcadas; no documentos.
- conflicts: entradas pendientes del manifiesto, incluidas las aún sin resolver.
- errors: entradas de errores por archivo de la indexación; incluyen errores de
  permisos/UTF-8/UUID/tamaño y diagnósticos de reconciliación, no solo fallos de lectura.
- orphans: registros del manifiesto con deleted=true, no documentos activos.

## Bloqueo, coherencia y recuperación

`.trama/.lock` es un archivo persistente vacío, modo inicial 0600. Nunca se elimina
al liberar un bloqueo. Linux libera flock cuando se cierra el descriptor o termina
el proceso. No es un archivo PID ni se interpreta su mera existencia como bloqueo.

`index` y `resolve --apply` mantienen LOCK_EX desde antes de leer el manifiesto
hasta terminar publicación/limpieza. `query`, `conflicts`, `resolve --preview` y
la API UI mantienen LOCK_SH durante toda la lectura/preparación. Todas las tomas
son LOCK_NB, sin espera/timeout/reintento automático: la GUI puede reintentar después.
Los bloqueos son independientes por espacio, entre procesos y entre llamadas
con descriptores diferentes. Se rechazan symlinks/hardlinks del archivo .lock.
Preparación/publicación interna reutiliza el bloqueo de su operación, sin anidar
flock sobre otro descriptor. No invocar helpers privados desde frontends.

Las lecturas UI no recuperan una publicación: con pending devuelven recovery_needed.
Los comandos tradicionales pueden recuperar: toman exclusión para terminar y, si
son lectores, vuelven a compartido. Ninguno puede observar un estado intermedio
producido por otro proceso que respete el protocolo. La UI abre SQLite mode=ro y
usa una transacción de lectura por llamada. Mantiene el bloqueo mientras consulta
tanto el manifiesto como SQLite. El snapshot termina al devolver la respuesta.

SQLite guarda `metadata.manifest_digest`: SHA-256 del JSON lógico del manifiesto,
serializado UTF-8 con claves ordenadas y separadores canónicos. Reordenar espacios
o claves en disco no lo invalida; cambiar datos sí. Una huella distinta o un índice
antiguo devuelve index_stale; index lo reconstruye con esquema 4 y guarda posiciones.
La huella detecta desincronización entre manifiesto e índice. El inspector añade
disk_state para cambios de metadatos del archivo seleccionado; no inspecciona todo
el disco, ni actualiza automáticamente búsqueda o enlaces. Un futuro watcher podría
solicitar indexación explícita.

El bloqueo es cooperativo/advisory para sistemas de archivos Linux con flock. No
impide ediciones externas de documentos ni modificaciones manuales de .trama; estas
siguen fuera de las garantías. No eliminar/reemplazar .lock a mano. Una lectura puede
crear .lock al abrir un espacio antiguo; solo escribe metadatos de coordinación,
no documentos. Nunca se instala una dependencia ni se inicia un servicio.

## Consumo por la futura ventana

GTK 4 en Arch/Xfce podrá importar esta API en un worker o ejecutar ui-query y parsear
stdout. No usar SQLite directamente ni bloquear el hilo del bucle gráfico. El panel
de búsqueda toma results; seleccionar un UUID solicita inspect_document, y la barra
de estado usa status. Mostrar needs_update, ambigüedad y errores como avisos visibles,
sin corregir documentos automáticamente. Tratar busy como reintentable y pedir una
indexación para recovery_needed/index_stale. El siguiente incremento puede ser una
ventana mínima de solo lectura o un fallback TUI; no hay GTK instalado en este cambio.


## Extensión de inspector en incremento 7

La envoltura se mantiene en versión 1. Se añaden parámetros y campos a inspect;
**backlinks y outgoing_links ahora contienen solo una página por defecto**. Los
clientes que asumían arrays completos deben seguir next_offset y total. No hay
cambio en los esquemas de Link ni de búsqueda, manifiesto v2 o SQLite v4.

Parámetros Python: link_limit entero 1..100 (por defecto 50), backlinks_offset y
outgoing_offset enteros 0..1_000_000 (por defecto 0). Los inválidos producen
invalid_request. Se aplican LIMIT/OFFSET directamente en SQLite: no se carga una
lista completa para cortarla en Python. Los totales cuentan ocurrencias; el campo
document.backlink_count sigue contando fuentes distintas. Existen índices sobre
links.source y links.target en las reconstrucciones nuevas; índices antiguos
siguen siendo legibles pero una reindexación añade esas optimizaciones.

```bash
PYTHONPATH=src .venv/bin/python -m trama_core ui-query .demo/espacio inspect Inicio.md --link-limit 50 --backlinks-offset 50 --outgoing-offset 0
```

`link_pages` tiene exactamente dos claves, backlinks y outgoing_links. Cada objeto
contiene limit, offset, total (enteros) y next_offset (entero o null). Se ordena por
position, igual que antes. Una página fuera del total devuelve array vacío y
next_offset=null. Los offsets son independientes; la consulta utiliza una única
transacción de lectura para los dos arrays y sus totales. No hay snapshot mantenido
entre llamadas: reindexar puede cambiar el orden o total entre páginas.

`disk_state` mantiene exactamente state y modified. Desde el incremento 8,
state puede ser current, metadata_only, modified, unknown, missing, unsafe,
unreadable, too_large o changing. modified es false en current/metadata_only,
true en modified y null en los demás. Se comparan size/device/inode/mtime_ns.
Si coinciden, no se lee contenido; si difieren, se lee como máximo MAX_BYTES+1
(2 MiB + 1), se valida estabilidad de stat antes/después y se calcula SHA-256.
Los symlinks se rechazan y un tamaño conocido superior al límite evita la lectura.

inspect añade tres campos en data:

- content_modified: true si SHA-256 difiere del registrado; false si se verificó
  igualdad; null si no hubo verificación o no pudo completarse.
- hash_verified: booleano; true solo tras una lectura estable y comparación.
- current_hash: SHA-256 calculado, o null si no se leyó el archivo.

Un touch con hash idéntico produce metadata_only/modified=false y no genera alarma
de edición. current indica metadatos iguales, no prueba de igualdad de contenido:
una edición que restaure todos los metadatos observados puede pasar inadvertida.
changing evita afirmar igualdad si el archivo cambia durante la lectura; too_large
respeta el límite sin calcular hash. No se releen todos los documentos del espacio.
Un registro anterior sin mtime_ns sigue dando unknown si no cambió otro metadato.
Para document=null los nuevos campos son null/false/null, respectivamente.

Un archivo modificado no vuelve inválido el índice derivado del manifiesto: la
respuesta sigue ok/ready, con el aviso disk_state=modified. index_stale se reserva
para el desfase SQLite/manifiesto. La UI muestra el aviso y ofrece la acción explícita
de reindexar. Ni refresh ni inspect escriben documentos o reindexan por sí solos.

Las acciones reindex_space y open_document viven en desktop_actions; son comandos
explícitos separados de esta API de lectura. La primera llama a index bajo EX; la
segunda valida la ruta y ejecuta argv sin shell. ui-window.md documenta sus opciones.


## Creación explícita nativa · incremento 8

La API de lectura conserva envoltura v1 y no crea notas. `notes.create_note(space,
name)` es un comando separado bajo flock EX, compartido por CLI y Presenter.
Devuelve ok/state/created/uuid/rel_path/error y, en éxito, title,
identity_source=frontmatter y result con los contadores de indexación.
Estados de error: busy, already_exists, create_error e index_error. created=true
con ok=false informa de un archivo nuevo conservado tras fallo: revisar el archivo
y reintentar index, sin recrearlo sobre la misma ruta. La apertura opcional del editor
es otra acción; un fallo del editor no elimina una nota creada correctamente.

Presenter.create_note(name) guarda creation_action en snapshot, actualiza el estado,
busca el título y selecciona el UUID generado. Conserva el historial anterior.
GTK ejecuta la creación en su worker; snapshot nunca escribe al arrancar.
