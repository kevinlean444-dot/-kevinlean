# Validación del primer incremento

Ejecutada en el entorno cloud con Python 3.12.14 y SQLite 3.53.1 / FTS5.
Comando: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.
Resultado del incremento 4: 40 pruebas ejecutadas, 40 correctas, sin omitidas.
Las 30 del incremento anterior siguen pasando, sin modificar sus tests.
Las 7 originales en test_core.py permanecen intactas. La antigua prueba de asignación
en documento se sustituyó por una de inmutabilidad; los tests CRLF usan index sin
opciones de escritura. --assign-ids debe ser rechazado por argparse antes de indexar.
La salida real completa está en [test-output.txt](test-output.txt).

Casos nuevos de test_imported_rename.py: renombre importado con nodo, manifiesto,
SQLite y backlinks estables; bytes originales intactos; reconstrucción; copia
coexistente sin fusión; ambigüedad 1→2 incluso con inode coincidente; rechazo de hash
como única evidencia; confirmación CLI de traslado con edición; declaración inválida
sin cambios de estado; eliminación de la opción de escritura.

También se conservan los tests de UUID embebido con renombre y edición simultánea,
colisión controlada, borrado/restauración, migración v1, Unicode, enlaces retirados,
front matter sin id intacto y CRLF/ID inválido. Se usó unittest, sin instalar pytest.

Casos: recorrido CLI completo; repetición y reconstrucción; originales idénticos
por SHA-256; enlaces resueltos, rotos y externos; títulos duplicados; contenido
duplicado con IDs distintos; Unicode y acentos; rutas con espacios; espacio vacío;
archivo sin permisos de lectura; symlinks externos de archivo y directorio;
escape relativo; límite de tamaño; UTF-8 inválido; UUID duplicado; estado inseguro;
entrada literal de búsqueda y consultas SQL parametrizadas.

Ejemplo del primer incremento ejecutado sobre `.demo/espacio`, copia de fixtures: 3 documentos, 6 enlaces,
sin errores de indexación. `search cafe` encontró Inicio.md; backlinks a
`Ideas de estudio.md` devolvió Inicio.md. Exportación JSON en `.demo/graph.json`.
La salida del ejemplo y el entorno virtual están ignorados por Git.

No se ha probado empaquetado instalable, otras versiones de Python, Arch, interfaz
gráfica, rendimiento ni sustitución concurrente maliciosa del espacio. El archivo
sin lectura se comprueba por bits de modo además del error del sistema para que
el caso sea reproducible incluso en ejecuciones con permisos elevados.


Incremento 3 — resolución posterior a indexar

Comando ejecutado: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.
Salida completa actual en [test-output.txt](test-output.txt). Siete tests nuevos en
`test_resolution.py`: ambigüedad post-index con preview sin mutación, aplicación,
reconexión de enlaces entrantes y salientes, copia independiente y reconstrucción;
traslado editado y CLI dry-run/apply; coexistencia física sin cambios de estado;
rutas ausentes/externas/symlinks/ID canónico rechazados; candidato editado desde index;
fallo al construir SQLite sin alterar el par anterior; interrupción entre los dos
reemplazos con recuperación automática antes de consultar el estado. Los snapshots
comparan bytes del manifiesto, SQLite y documentos en los rechazos y preview.

Se ejecutó `.venv/bin/python docs/demo-resolution.py` sobre un espacio nuevo
`.demo/espacio/incremento3`. Resultado: conflicto 1→2 inspeccionado, preview y apply
correctos, backlink recuperado desde referencia.md y hashes Markdown intactos.
Salida guardada en `.demo/incremento3-output.txt` (ignorada por Git).

Las pruebas de fallos inyectan excepciones controladas; no simulan cortes eléctricos
reales ni certifican durabilidad de todos los sistemas de archivos. No se verificó
concurrencia entre procesos, aún no soportada, ni integración con GTK.


Incremento 4 — bloqueo por espacio y contrato UI

Comando ejecutado: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.
Diez pruebas nuevas en test_ui_contract.py, sin instalar paquetes:

- Proceso hijo con EX: index y resolve --apply desde procesos independientes fallan
  inmediatamente con mensaje Espacio ocupado; la UI devuelve busy. Manifiesto,
  SQLite y documentos quedan idénticos. Tras liberar el bloqueo se puede indexar.
- Proceso hijo con SH: una segunda lectura funciona, una escritura se rechaza.
- Un bloqueo en un espacio no bloquea otro espacio independiente.
- Inspector de nota renombrada y resuelta: backlinks históricos needs_update=true,
  línea/contexto, enlace roto y ambiguo con UUID candidatas, todo en una respuesta.
  Se prohíben lecturas de originales con mock y se comparan snapshots byte a byte.
- Contadores exactos: 6 notas, 3 enlaces, 1 pendiente de actualización, 1 roto,
  1 ambiguo, 1 conflicto y 1 error, con inspección de candidata y archivo inválido.
- Búsqueda con relevancia, desempate estable, snippets Unicode, advertencias y
  paginación; entrada de operadores se trata como frase literal.
- Origen frontmatter y ficha de registro ilegible fuera de la proyección activa.
- Índice ausente/antiguo/corrupto, manifiesto desincronizado/inválido y documento no
  encontrado producen respuestas estructuradas. CLI usa stdout JSON y código 1.
- Interrupción real simulada entre reemplazos: la UI devuelve recovery_needed sin
  alterar nada; index recupera y devuelve el contrato a ready.
- Symlink de .lock rechazado sin modificar el documento al que apunta.

Prueba manual de CLI sobre el espacio existente .demo/espacio:
index devolvió 9 documentos, 8 enlaces y cero errores; search cafe devolvió Inicio.md
con snippet [café]; inspect de Ideas de estudio.md devolvió dos ocurrencias de
backlink desde Inicio.md, en líneas 2 y 3, y su enlace saliente. status devolvió
8 notas, 1 adjunto, 8 enlaces, 3 unresolved, 1 external, sin errores ni conflictos.
Ese espacio incluye los subdirectorios de ejemplos previos; no equivale al fixture
mínimo de 3 documentos que sigue validado por las pruebas automatizadas.

La salida completa del último run está en test-output.txt. No se midió latencia ni
se instaló/probó GTK, Arch/Xfce o sistemas de archivos remotos. flock es cooperativo;
editores y scripts externos que ignoren el bloqueo siguen fuera de garantías.
