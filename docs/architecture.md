# Arquitectura y decisiones

Estado construido: CLI Python sin dependencias de ejecución externas, SQLite FTS5.
Arch x86_64 y Xfce siguen siendo objetivos futuros; no son requisitos del núcleo.
GTK 4 y Archiso no se utilizan todavía. No hay editor ni creador de notas.

Los archivos alimentan documentos y texto FTS; los enlaces explícitos generan aristas.
El manifiesto v2 mantiene registros y destinos de enlaces por UUID; SQLite contiene una vista derivada reemplazada
mediante transacción. La publicación preparada y su marcador permiten terminar una actualización interrumpida.
Eliminar solamente index.sqlite permite reconstruir documentos y relaciones con los
mismos UUID. No hay descargas, ejecución de contenido ni detección semántica.

Límites: 2 MiB por archivo, 10000 archivos visibles. Carpetas y archivos ocultos
se omiten. Todos los symlinks se omiten. Adjuntos se leen solamente para calcular
hash y no se interpretan. Errores de lectura, UTF-8 o UUID se registran por archivo.
El espacio debe permanecer estable durante la indexación: no se ofrece aislamiento
frente a otro proceso que sustituya directorios o archivos simultáneamente.
No ejecutar sobre directorios que contengan secretos: Trama no puede identificar
secretos dentro de documentos normales. Elegir explícitamente un espacio de prueba.
Markdown usa un subconjunto deliberado: enlaces de una línea sin paréntesis anidados;
no es un parser CommonMark y puede reconocer sintaxis dentro de bloques de código.

Incremento 2: la indexación nunca escribe notas, ni con opciones. Se retiró
--assign-ids. Los importados se reconcilian tras observar todo el espacio: ruta
anterior ausente, correspondencia unívoca, mismo hash/tamaño/dispositivo/inode.
Esto distingue renombre local de copia coexistente, sin usar el hash como identidad.
La evidencia es heurística: no garantiza reconocer copia+borrado ni edición simultánea.
--relocate UUID RUTA declara explícitamente un traslado importado antes de registrar
el destino. Un UUID embebido sigue siendo canónico aunque cambie todo el contenido.

Los conflictos quedan en el manifiesto y su proyección SQLite. Los metadatos
adicionales son compatibles con v2; SQLite se reconstruye como user_version=3 y
el grafo exporta versión 3. `needs_update` expone destinos mantenidos por historial;
se preservan el nodo y los backlinks pero nunca se reescriben enlaces originales.
El recorrido completo evita que el orden de descubrimiento convierta copias en
renombres. Sin nueva dependencia ni instalaciones. Solo se escribe bajo .trama.
Incremento 3: reconciliation.py implementa conflicts y resolve (preview por defecto).
La resolución explícita retira el UUID provisional, preserva el histórico, remapea
fuentes y destinos y registra auditoría en resolutions. No modifica Markdown/TXT.
index puede preparar toda su proyección en memoria sin persistirla; resolve usa
ese mismo camino para mostrar el resultado que aplicará. core.publish prepara
SQLite y manifiesto y usa un marcador pending para recuperación antes de leer.
Esto reemplaza la escritura anterior de manifiesto antes de construir SQLite.
La base se puede reconstruir preservando identidad, backlinks y conflictos resueltos.

La publicación es recuperable entre reemplazos, no atómica para lectores externos
ni segura ante escritores concurrentes. El espacio debe permanecer estable y con
una sola operación activa. Este límite debe resolverse antes de permitir procesos
GUI y CLI escribiendo a la vez.

Próximo paso: diseñar el contrato de lectura para la ventana mínima de búsqueda y
backlinks: errores estructurados, versiones, límites/paginación y needs_update.
El núcleo ya permite diseñarlo sin implementar aún GTK. Antes de conectar una GUI
que indexe simultáneamente se necesita bloqueo por espacio y tests de concurrencia.

Roadmap posterior: núcleo fiable → ventana mínima de búsqueda/backlinks → integración
Xfce → evaluación de distribución Arch. Sin promesas de rendimiento o compatibilidad.
