# Validación del primer incremento

Ejecutada en el entorno cloud con Python 3.12.14 y SQLite 3.53.1 / FTS5.
Comando: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.
Resultado del incremento 3: 30 pruebas ejecutadas, 30 correctas, sin omitidas.
Las 23 del incremento anterior siguen pasando.
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
