# Arquitectura y decisiones

Estado construido: CLI Python sin dependencias de ejecución externas, SQLite FTS5.
Arch x86_64 y Xfce siguen siendo objetivos futuros; no son requisitos del núcleo.
GTK 4 y Archiso no se utilizan todavía. No hay editor ni creador de notas.

Los archivos alimentan documentos y texto FTS; los enlaces explícitos generan aristas.
El manifiesto v2 mantiene registros y destinos de enlaces por UUID; SQLite contiene una vista derivada reemplazada
mediante transacción. Guardar el manifiesto antes permite repetir una indexación fallida.
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

Identidad ante renombrados implementada para UUID embebido; hash nunca fusiona
identidades. SQLite v2 incluye lápidas deleted. La generación de UUID en Markdown
es explícita con --assign-ids; sin la opción se mantienen originales intactos.
Próximo incremento: diagnóstico visible de enlaces mantenidos por historial y
resolución asistida de colisiones. No reconciliar notas sin UUID por hash.
Roadmap posterior: núcleo fiable → ventana mínima de búsqueda/backlinks → integración
Xfce → evaluación de distribución Arch. Sin promesas de rendimiento o compatibilidad.
