# Formato v2

Espacio: directorio explícito, sin symlinks en la ruta. Markdown y TXT UTF-8 son
notas; otros archivos visibles son adjuntos. Las rutas exportadas son relativas,
con `/`. `.trama/manifest.json` contiene `version: 2`, `documents` y `bindings`.
Conservar este manifiesto: no es una caché. `.trama/index.sqlite` sí es desechable.

Markdown acepta al comienzo front matter con `id: <UUIDv4>` (también entre
comillas simples o dobles). Se valida el UUID; un ID inválido o de otra versión
es error por archivo, nunca se reemplaza automáticamente. Se admite LF y CRLF.
No hay parser YAML general: solo campo id escalar simple, una vez, sin comentarios.

`index` no modifica documentos. `index --assign-ids` inserta un campo UUIDv4 en
Markdown sin ID: reutiliza la identidad del manifiesto si existe y preserva el
resto de bytes, front matter y permisos. Usa reemplazo atómico local y rechaza
hardlinks y symlinks. Un fallo antes del reemplazo deja el original intacto.
El espacio debe permanecer estable durante la operación. TXT y adjuntos mantienen
identidad local sin escritura. Sin UUID embebido no se puede reconocer un traslado.

`documents` mapea UUID → `{rel_path, content_hash, title, kind, deleted}`.
La ruta y el hash son atributos mutables; jamás se usan hashes para fusionar.
Al reaparecer un UUID en otra ubicación se actualiza el mismo registro. Una ruta
inexistente sin reubicación marca deleted; SQLite conserva la lápida con deleted=1.
Archivos con error aún presentes no se consideran borrados, pero quedan fuera de
la proyección activa. Dos rutas con UUID igual generan error explícito: se conserva
el primero según recorrido ordenado, se excluye el segundo; resolver manualmente.

Migración v1 → v2 automática durante indexación, manteniendo UUID por ruta. Una
migración con varias rutas para el mismo UUID se rechaza antes de escribir estado,
pues no permite distinguir traslado de colisión con seguridad. SQLite se reconstruye
transaccionalmente con user_version=2; ejecutar index antes de consultar índices v1.

`bindings` guarda `[UUID fuente, texto del enlace]` serializado como clave → UUID
destino. La resolución actual por ruta/título tiene prioridad. Si no hay destino
actual, se reutiliza el destino anterior solo si su UUID está activo; si está borrado
el enlace queda unresolved y se retiene la referencia para una posible restauración.
No se reutilizan bindings ante ambigüedad, enlaces externos o rutas inseguras.
Quitar el enlace del documento elimina su binding. Un enlace que nunca se resolvió
no obtiene destino por historial ni por coincidencia de contenido. Conservar el
manifiesto permite reconstruir estos enlaces incluso después de mover documentos.

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
version=2, documents activos, deleted_documents, links y errors; candidates contiene IDs, target puede ser null.
