# Registro de validación de Trama

Entorno de incrementos 5–7: Python 3.13.5 del sistema, SQLite 3.46.1/FTS5, PyGObject 3.50.0,
GTK 4.18.6 en Debian 13 amd64 bajo Xvfb. Se preservó el venv previo Python 3.12.14
con el que se habían validado los incrementos 1–4 (SQLite 3.53.1).

Comando real de la suite completa:

```bash
. scripts/gtk-env.sh
xvfb-run -a dbus-run-session -- env GTK_A11Y=none GSK_RENDERER=cairo G_DEBUG=fatal-warnings PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Resultado del incremento 7: 55 pruebas ejecutadas, 55 correctas, sin omitidas.
Las 49 anteriores siguen pasando; solo se corrigió el cierre de conexiones SQLite
en tres fixtures, sin cambiar sus aserciones.
Salida real completa: test-output.txt.

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

No se ha probado empaquetado instalable, Arch/Xfce, rendimiento ni sustitución
concurrente maliciosa del espacio. La interfaz GTK sí se probó bajo Xvfb en este incremento. El archivo
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
reales ni certifican durabilidad de todos los sistemas de archivos. En ese incremento no se verificó concurrencia ni GTK; las pruebas de los
incrementos 4 y 5 siguientes cubren esos caminos.


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

En el incremento 4 no se midió latencia ni se probó GTK, Arch/Xfce o sistemas
de archivos remotos. El incremento 5 añade pruebas GTK reales. flock es cooperativo;
editores y scripts externos que ignoren el bloqueo siguen fuera de garantías.


Incremento 5 — presentador, GTK real y terminal

- Cuatro pruebas nuevas de Presenter/TUI: búsqueda/selección, navegación desde
  backlink y saliente resuelto, historial Atrás, bloqueo/error/recuperación,
  snapshot inmutable, paridad entre vistas, salida terminal y fallback sin display.
- Una prueba nueva de Gtk.Application real: abre el espacio de fixture, ejecuta
  búsqueda, pulsa botón de resultado, comprueba ventana mapeada, título, UUID,
  resultados, backlinks con Actualizar enlace y línea de origen, salientes rotos y
  ambiguos y barra de estado. Se ejecuta en proceso separado con G_DEBUG=fatal-warnings
  y PYTHONWARNINGS=error, exige stderr vacío y cierre limpio de GTK/GLib.
- Los snapshots de bytes de Markdown/TXT, manifiesto y SQLite antes/después coinciden.
  El test del controlador prohíbe read_document mediante mock: solo consume contrato.
- Smoke manual bajo Xvfb sobre .demo/espacio: GTK [4,18,6], título Inicio, 1 resultado,
  1 backlink, mapped=true, verified=true. No es una ventana simulada ni HTML.
- Runtime descargado de APT con firmas/HTTPS conservadas; paquetes extraídos bajo
  .runtime-gtk por falta de permisos de administración. No se ejecutó sudo ni se
  instalaron paquetes globalmente. docs/ui-window.md lista dependencias y alternativas.

La prueba GTK se omite explícitamente si se ejecuta sin display o gi; esa ejecución
no demostraría la ventana. El comando Xvfb de este registro ejecutó las 45 sin
omisiones. No se certifica Arch/Xfce real, HiDPI, tecnologías de asistencia ni
rendimiento; la GUI añade paginación visual en el incremento 6, pero sigue sin watcher ni editor.


Incremento 6 — teclado, foco y páginas limitadas

Cuatro pruebas nuevas en test_ui_keyboard.py:

- Controlador sin GTK: flechas seleccionan/inspeccionan resultados y cruzan páginas;
  Enter abre la fuente de un backlink, Atrás restaura el UUID anterior y los enlaces
  ambiguos/rotos no abren una nota inventada. Se comprueban ciclo y reverso de foco,
  Escape contextual y snapshots de bytes antes/después.
- Colección de 137 notas: páginas 50/50/37, límites de primera/última página,
  reinicio de consulta, resultados vacíos y recorrido completo por flechas. Una sola
  página permanece en estado y el historial nunca supera 100 entradas.
- CLI: page-size común en snapshot y TUI; tamaños fuera de 1..100 se rechazan, también
  antes de activar GTK. El rango visible coincide con total y lote recibido.
- GTK real bajo Xvfb: Gtk.EventControllerKey unido a la ventana en captura; señales
  key-pressed para Ctrl+F, / dentro/fuera de edición, flechas, AvPág, Tab/Shift+Tab,
  Enter, Alt+Izquierda, Backspace editable y Escape. Verifica foco/pestañas, selección
  del texto, inspección del resultado y navegación histórica, render sin reconstruir
  botones de resultados, mantenimiento del caret y botón de navegación al refrescar.
  Doscientas búsquedas solicitadas sin drenar el loop permanecen agrupadas en una
  ejecución y como máximo una pendiente. Se comprueban stderr vacío, avisos GTK y
  Python fatales, cierre limpio y bytes intactos de todo el espacio.

Comando ejecutado (igual que el incremento gráfico anterior):

```bash
. scripts/gtk-env.sh
xvfb-run -a dbus-run-session -- env GTK_A11Y=none GSK_RENDERER=cairo G_DEBUG=fatal-warnings PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Último resultado: `Ran 49 tests in 2.966s`, `OK`. Sin omitidas. El tiempo es solo la
salida de unittest en este contenedor; no es una medida de latencia de interacción.
No se midieron RSS/CPU ni se probó teclado físico o lector de pantalla en Arch/Xfce.
La evidencia comprueba límites de estructuras/widgets y eventos del controlador GTK;
en ese incremento el inspector todavía usaba el payload completo; el incremento 7
lo reemplaza por consultas paginadas.


Incremento 7 — inspector paginado y acciones explícitas de escritorio

Seis pruebas nuevas en test_inspector_actions.py:

- Contrato y controlador con 125 backlinks y 125 salientes: solo 50 por sección en
  la primera respuesta, totales exactos, páginas 50/50/25 independientes, offsets
  inválidos, flechas que cruzan página y activación del backlink de la página actual.
  Se comprueba también que reducir el total al editar/reindexar corrige offsets.
- Nota editada por el usuario: refresh detecta modified sin escribir; reindexar bajo
  un bloqueo ajeno devuelve busy sin alterar el par SQLite/manifiesto; después de
  liberarlo actualiza título/metadata y da current, conservando los bytes editados.
- Apertura externa con runner simulado: argv exacto, shell=False, close_fds y sesión
  nueva; nombres con espacios/metacaracteres no se evalúan. VISUAL tiene prioridad
  y dry-run no llama al runner. Se comparan bytes antes/después.
- Rechazo de rutas externas, escapes, archivos ausentes y symlinks sin lanzar nada.
- Archivo cambiado mientras se lee para indexar: error por archivo, sin asociar el
  contenido anterior con metadatos nuevos ni sobrescribir el cambio del usuario.
- GTK real bajo Xvfb: máximo 50 botones en cada sección, páginas 50/50/25, Ctrl+R
  detecta edición, Ctrl+Shift+R reconstruye el índice y Ctrl+O dry-run prepara el
  programa configurado sin ejecutar un editor real. Compara todos los documentos,
  descontando solamente la edición deliberada hecha por la fixture. Exige stderr
  vacío con avisos GTK/Python fatales y cierre limpio del bucle.

Comando real:

```bash
. scripts/gtk-env.sh
xvfb-run -a dbus-run-session -- env GTK_A11Y=none GSK_RENDERER=cairo G_DEBUG=fatal-warnings PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Salida final: `Ran 55 tests in 2.708s`, `OK`, sin omisiones ni avisos. El log completo
es test-output.txt. Se eliminaron ResourceWarning de Python 3.13 al cerrar las
conexiones de tres fixtures antiguas con contextlib.closing; no se desactivó ninguna
advertencia ni prueba. No se midió RSS/CPU ni se abrió un editor gráfico externo
real: se verificó su argv y el rechazo de rutas mediante inyector y dry-run.
La detección modified se basa en metadatos, no demuestra igualdad de contenido.
