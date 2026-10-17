# Validación del primer incremento

Ejecutada en el entorno cloud con Python 3.12.14 y SQLite 3.53.1 / FTS5.
Comando: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.
Resultado del incremento de identidad: 16 pruebas ejecutadas, 16 correctas, sin omitidas
(7 originales sin modificar y 9 nuevas en tests/test_identity.py).

Nuevos casos: renombrado y reconstrucción con backlinks; traslado más cambio de
contenido y título; hashes iguales con identidades distintas; colisión controlada;
asignación explícita e idempotente; borrado y restauración; migración v1 → v2;
CRLF e ID existente intacto y rechazo de ID inválido; eliminación de bindings al
quitar un enlace del documento. Se usó unittest, el runner existente, sin instalar pytest.

Casos: recorrido CLI completo; repetición y reconstrucción; originales idénticos
por SHA-256; enlaces resueltos, rotos y externos; títulos duplicados; contenido
duplicado con IDs distintos; Unicode y acentos; rutas con espacios; espacio vacío;
archivo sin permisos de lectura; symlinks externos de archivo y directorio;
escape relativo; límite de tamaño; UTF-8 inválido; UUID duplicado; estado inseguro;
entrada literal de búsqueda y consultas SQL parametrizadas.

Ejemplo ejecutado sobre `.demo/espacio`, copia de fixtures: 3 documentos, 6 enlaces,
sin errores de indexación. `search cafe` encontró Inicio.md; backlinks a
`Ideas de estudio.md` devolvió Inicio.md. Exportación JSON en `.demo/graph.json`.
La salida del ejemplo y el entorno virtual están ignorados por Git.

No se ha probado empaquetado instalable, otras versiones de Python, Arch, interfaz
gráfica, rendimiento ni sustitución concurrente maliciosa del espacio. El archivo
sin lectura se comprueba por bits de modo además del error del sistema para que
el caso sea reproducible incluso en ejecuciones con permisos elevados.
