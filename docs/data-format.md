# Formato v2

Espacio: directorio explícito, sin symlinks en la ruta. Markdown y TXT UTF-8 son
notas; otros archivos visibles son adjuntos. Las rutas exportadas son relativas,
con `/`. `.trama/manifest.json` contiene `version: 2`, `documents` y `bindings`.
Conservar este manifiesto: no es una caché. `.trama/index.sqlite` sí es desechable.

Markdown acepta al comienzo front matter con `id: <UUIDv4>` (también entre
comillas simples o dobles). Se valida el UUID; un ID inválido o de otra versión
es error por archivo, nunca se reemplaza automáticamente. Se admite LF y CRLF.
No hay parser YAML general: solo campo id escalar simple, una vez, sin comentarios.

`index` no modifica documentos bajo ninguna opción. `--assign-ids` y la función
de escritura de UUID se han eliminado. Una nota importada, incluso con front matter
sin id, conserva identidad exclusivamente en el manifiesto; nunca se inyecta contenido.

Reconciliación automática al completar el recorrido:

1. Notas con UUID explícito se reconocen por ese UUID, aunque cambie su contenido.
2. Notas importadas en una ruta registrada conservan su UUID local.
3. Para una ruta anterior desaparecida, se consideran solo archivos nuevos sin UUID
   explícito y aún no registrados, del mismo tipo y hash. Debe haber una única
   candidata y un único registro desaparecido candidato. Además deben coincidir
   tamaño, dispositivo e inode previamente observados. Solo entonces se transfiere
   el UUID. El hash solo delimita candidatas; no identifica ni fusiona entidades.
4. Si la ruta anterior existe, una copia nueva recibe un UUID independiente.
5. Si hay varias candidatas o varios registros desaparecidos compatibles, no se
   transfiere ningún ID. Se registra error `Renombre ambiguo` y se asignan UUID nuevos
   independientes. El registro anterior se conserva como deleted. `conflicts` guarda
   el diagnóstico histórico `{id, old_path, candidates}` y graph lo exporta como
   `identity_conflicts`, incluso al reindexar o reconstruir. Los errores del ciclo
   se limpian en el siguiente index; el historial permanece.
6. Un hash único sin evidencia de inode no permite decidir: se registra `Renombre no
   confirmado`. Si se necesita confirmar manualmente, hacerlo antes de indexar la
   nueva ruta mediante `index ESPACIO --relocate UUID RUTA_RELATIVA`. La ruta anterior
   debe haber desaparecido y el destino ser legible, nuevo y sin ID explícito.
   Esta declaración permite cambios de contenido y transfiere solo el UUID indicado;
   no mueve ni escribe archivos. Una declaración inválida aborta antes de guardar
   manifiesto o SQLite. Solo se admite una declaración por ejecución.

Los campos adicionales del registro son `size`, `device`, `inode`, `explicit_id` y
`previous_paths`. Son extensiones aditivas del manifiesto v2, no se cambia su versión.
Un manifiesto antiguo necesita una indexación en la ubicación original para recoger
estos metadatos antes del primer renombre automático. No se usa inode para resolver
ambigüedad de contenido. Inode puede reutilizarse: es una heurística conservadora,
no prueba histórica; no se garantiza reconocer copia+borrado, cambios entre sistemas
de archivos, renombre+edición sin UUID ni cambios concurrentes. En esos casos usar
confirmación explícita antes de indexar. Para destinos ya registrados usar `resolve` con vista previa y aplicación explícita,
como se documenta a continuación.

`documents` mapea UUID → `{rel_path, content_hash, title, kind, deleted, size, device, inode, explicit_id, previous_paths}`.
La ruta y el hash son atributos mutables; jamás se usan hashes para fusionar.
Al reaparecer un UUID en otra ubicación se actualiza el mismo registro. Una ruta
inexistente sin reubicación marca deleted; SQLite conserva la lápida con deleted=1.
Archivos con error aún presentes no se consideran borrados, pero quedan fuera de
la proyección activa. Dos rutas con UUID igual generan error explícito: se conserva
el primero según recorrido ordenado, se excluye el segundo; resolver manualmente.

Migración v1 → v2 automática durante indexación, manteniendo UUID por ruta. Una
migración con varias rutas para el mismo UUID se rechaza antes de escribir estado,
pues no permite distinguir traslado de colisión con seguridad. SQLite se reconstruye
transaccionalmente con user_version=4; ejecutar index antes de consultar índices antiguos.

`bindings` guarda `[UUID fuente, texto del enlace]` serializado como clave → UUID
destino. La resolución actual por ruta/título tiene prioridad. Si no hay destino
actual, se reutiliza el destino anterior solo si su UUID está activo; si está borrado
el enlace queda unresolved y se retiene la referencia para una posible restauración.
No se reutilizan bindings ante ambigüedad, enlaces externos o rutas inseguras.
Quitar el enlace del documento elimina su binding. Un enlace que nunca se resolvió
no obtiene destino por historial ni por coincidencia de contenido. Conservar el
manifiesto permite reconstruir estos enlaces incluso después de mover documentos.
Los enlaces resueltos por historial llevan `needs_update=1`: actualizar su texto
manualmente; no se reescriben notas. Una resolución actual lleva needs_update=0.
previous_paths conserva las rutas previas, pero no permite resolver enlaces nuevos
a rutas antiguas automáticamente.

Título: primer encabezado `#`, o nombre sin extensión. `[[Título]]` compara el título
completo con casefold Unicode; no elimina acentos. Cero destinos: unresolved; varios:
ambiguous y lista de candidatos, sin arista elegida. Enlaces Markdown relativos se
resuelven desde la carpeta de la nota, decodifican porcentajes y omiten fragmento/query.
No se admiten títulos opcionales Markdown, alias wiki ni selección de encabezados.
Rutas absolutas, symlinks o escapes: outside; URI con esquema o dominio: external,
sin descarga. URI mal formada: invalid, conservada sin destino.
Enlaces rotos permanecen visibles. Una arista resolved puede apuntar a un adjunto.
Backlinks acepta UUID o ruta exacta; no el título ambiguo.

FTS5 usa unicode61 remove_diacritics=2: búsqueda por frase literal, sin operadores
aportados por usuario, insensible a mayúsculas y diacríticos latinos (cafe encuentra
café). No promete normalización lingüística para todos los alfabetos. Graph exporta
version=3, identity_conflicts, documents activos, deleted_documents, links y errors; candidates contiene IDs, target puede ser null.


Incremento 3: inspección y resolución posterior a indexar

```bash
PYTHONPATH=src .venv/bin/python -m trama_core conflicts ESPACIO
PYTHONPATH=src .venv/bin/python -m trama_core conflicts ESPACIO --json
PYTHONPATH=src .venv/bin/python -m trama_core resolve ESPACIO OLD_UUID RUTA_O_UUID
PYTHONPATH=src .venv/bin/python -m trama_core resolve ESPACIO OLD_UUID RUTA_O_UUID --preview
PYTHONPATH=src .venv/bin/python -m trama_core resolve ESPACIO OLD_UUID RUTA_O_UUID --apply
```

`conflicts` ordena UUID históricos y candidatas por ruta/UUID. Incluye registros
borrados y conflictos pendientes, hash anterior, todas las candidatas activas del
mismo tipo sin ID canónico, sus UUID/hash, si coinciden por hash o figuraban en el
conflicto, presencia de la ruta original, número de bindings históricos y de aristas
entrantes actualmente indexadas. Las candidatas son opciones de inspección, no una
propuesta de identidad; pueden tener contenido diferente. Metadatos son los del
último index. La salida textual muestra la misma información principal; --json es
la representación estructurada para herramientas.

`resolve` no aplica por defecto; --preview y --dry-run son equivalentes. --apply
es mutuamente excluyente con ambos. La vista previa incluye UUID superviviente y
retirado, registros antes/después, cambios de documentos, bindings antes/después,
enlaces retirados/añadidos con status y needs_update, errores de indexación y
conflictos que se resuelven. No escribe un manifiesto ni una base de datos temporal.
La aplicación recalcula y revalida el plan: no ejecuta una vista previa guardada.
No cambiar el espacio entre comandos si se desea el mismo plan.

La confirmación exige UUID histórico deleted, ruta antigua físicamente ausente
(también rechaza symlinks), destino activo y legible dentro del espacio y sin ID
canónico. El hash actual del destino debe coincidir con el indexado; de otro modo
reindexar. También se rechazan documentos nuevos, editados, ausentes o ilegibles
desde la última indexación en el resto del espacio: primero reindexar para que el
plan no incorpore asignaciones inesperadas. Rechaza archivos coexistentes, rutas fuera del espacio, symlinks, tipos
incompatibles, colisiones de UUID y bindings contradictorios. Un ID del front matter
no se sobrescribe ni se absorbe.

La operación copia atributos actuales bajo OLD_UUID y elimina CURRENT_UUID de
`documents`; no queda un segundo nodo, ni siquiera como deleted. Remapea UUID tanto
en fuentes como destinos de bindings y reconstruye todas las aristas. Los enlaces
históricos recuperables quedan resolved con needs_update=1; los que apuntan a la
ruta actual siguen resolved con needs_update=0. Un enlace ambiguo sigue ambiguo:
no se fuerza una elección distinta de las reglas habituales. Las otras candidatas
conservan sus identidades. Los conflictos cuyo id es OLD_UUID salen de `conflicts`
y se archivan en `resolutions`: `{id, retired_id, old_path, rel_path,
resolved_conflicts}`. Los registros de auditoría no son nodos consultables. El
manifiesto sigue en versión 2 y SQLite en 4 y grafo en 3, sin migración nueva necesaria.

Publicación recuperable del estado

SQLite y JSON no comparten transacción. Se construyen primero `index.next.sqlite`
(con transacción y cierre) y `manifest.next.json`; se sincronizan ambos. Un marcador
`pending` publicado por reemplazo atómico expresa la intención de terminar. Luego
se reemplazan SQLite y manifiesto y se retira el marcador, sincronizando el directorio.
Antes del marcador, un fallo conserva el par anterior. Después del marcador, el
siguiente comando completa ambos reemplazos pendientes antes de exponer estado.
Se verifican symlinks/hardlinks de todos los archivos de estado, incluidos temporales.
No borrar estos archivos manualmente durante recuperación. Esto ofrece recuperación
ante interrupción entre reemplazos, no una transacción entre archivos para lectores
externos que omitan la CLI. El incremento 4 protege comandos públicos con flock por espacio (EX para escritores,
SH para lectores), como se detalla en docs/ui-contract.md. No cambiar documentos
externamente durante la indexación. Una vista previa
normal no escribe nada; si encuentra una aplicación previa interrumpida, primero
termina esa recuperación pendiente, como cualquier otro comando.


Extensión del índice en incremento 4: SQLite user_version=4 incluye `metadata`
(key/value con manifest_digest) y `link_locations` (position/line/context). El
manifiesto permanece en v2, el grafo heredado en v3 y el nuevo contrato UI en v1.
Reindexar actualiza índices anteriores sin modificar originales. El archivo .lock
es estado de coordinación permanente, no parte del manifiesto ni de su huella.

Incremento 7 añade mtime_ns opcional a cada registro observado al indexar. No cambia
la identidad ni el hash; permite avisar de modificaciones por metadatos sin releer
contenido desde el inspector. Un manifiesto anterior sigue siendo válido, con estado
de disco unknown hasta reindexar si los demás metadatos siguen iguales.


Incremento 8 — creación nativa exclusiva

`new ESPACIO "Título o ruta relativa.md"` crea solo Markdown nuevo. Si falta .md,
se añade; el título es el nombre final sin esa extensión. Los padres deben existir.
Se rechazan rutas absolutas, .., componentes ocultos y caracteres de control.
El frontmatter escrito es YAML compatible con escalares entre comillas JSON
(Unicode, comillas y dos puntos escapados sin depender de un parser YAML):

```yaml
---
id: 83094492-4130-47c3-8d34-4affcc48e155
title: "Mi primera nota"
---

# Mi primera nota
```

Se genera UUIDv4; nunca se inyecta un ID en un archivo importado. El encabezado
Markdown replica el título para el parser actual, que sigue sin ser YAML completo.
El manifiesto v2 usa explicit_id=true, y el contrato ofrece
identity_source=identity_origin=frontmatter. No cambian SQLite v4 ni grafo v3.

Bajo un único flock EX se valida el estado previo sin publicarlo, se recorre el
padre con descriptores O_DIRECTORY|O_NOFOLLOW, y se abre el destino con
O_CREAT|O_EXCL|O_NOFOLLOW, modo 0600. Un archivo, directorio o symlink existente,
incluso colgante, provoca error; nunca se trunca ni se sustituye. Tras escribir y
sincronizar archivo/directorio, se prepara y publica el par índice/manifiesto con
el protocolo pending ya documentado. No hay bloqueo anidado ni cambios a otras notas.
La validación previa y la indexación posterior recorren el espacio con los límites
habituales; crear una nota no es una actualización incremental del índice.

El archivo nuevo y el estado derivado no forman una sola transacción. Si falla la
escritura o indexación posterior, created=true/ok=false advierte que se conserva el
archivo (posiblemente incompleto si falló la escritura); revisar su contenido y
reintentar index. Nunca se borra una nota para ocultar un fallo. Una interrupción de
publicación se recupera mediante pending; las identidades nativas se reconstruyen
desde frontmatter. Las reglas de duplicados y resolución de IDs siguen vigentes.

El inspector ahora compara SHA-256 cuando difieren los metadatos observados; touch
sin cambio de bytes produce metadata_only y content_modified=false. No escribe
los metadatos nuevos en el manifiesto: index explícito actualiza esa observación.
