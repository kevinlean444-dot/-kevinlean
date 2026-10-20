# Ventana mínima de Trama · incremento 5

Ventana real GTK 4 de solo lectura, más TUI y snapshot. Consume exclusivamente el
[contrato UI v1](ui-contract.md). No indexa automáticamente, no escribe documentos,
solo abre archivos locales mediante una acción explícita, no instala paquetes al arrancar y no necesita cuenta ni privilegios.

## Arquitectura

`trama_core.ui.Presenter` conserva status, query/search, inspection, UUID seleccionado,
historial y avisos. Solo llama a `ui_contract.status`, `search` e `inspect_document`.
Las vistas no abren SQLite ni los documentos para enriquecer el resultado. Un snapshot
es una copia del estado, con `ui_version=1`; los tres payloads interiores mantienen
sus envolturas del contrato v1. El historial no se persiste.

`ui/gtk.py` contiene Gtk.Application y Gtk.ApplicationWindow. Un ThreadPoolExecutor
con un solo worker ejecuta las consultas secuencialmente. Solo GLib.idle_add lleva
snapshots completos al hilo principal; tickets descartan la representación de
respuestas anteriores cuando ya se solicitó otra operación. La búsqueda tiene un
debounce adicional de 200 ms. Ninguna llamada al contrato se hace desde callbacks
GTK del hilo principal. No se mide ni promete una latencia concreta.

Diseño: cabecera con Atrás/Actualizar, Gtk.Paned con buscador y resultados a la
izquierda, título/metadatos y pestañas Backlinks/Enlaces salientes/Avisos a la derecha,
barra inferior con contadores. Los botones de backlink abren la fuente; los salientes
resueltos abren el destino; los rotos, ambiguos y externos no abren nada. Atrás vuelve
al UUID previo. Fallar una selección no añade un paso al historial. Se muestra una página de 50 resultados por defecto, configurable con --page-size
(1..100); las páginas anteriores se reemplazan, no se acumulan.

CSS local en ui/style.css: beige #f3eadb, papel #fffaf1, café #35251b y encabezados
#e5d4bc. Amarillo suave identifica Actualizar enlace/busy/recovery_needed; rojo claro
marca enlaces rotos; malva marca ambigüedad. Los estados tienen texto además del
color. Labels usan texto plano, nunca markup de notas ni shell. Fuentes y escalado
los aporta GTK; no se descargan recursos visuales.

`busy` conserva el funcionamiento del bucle gráfico y muestra aviso; Actualizar
reconsulta. `recovery_needed`, index_missing e index_stale se muestran sin ejecutar
una escritura automática: indexar desde CLI cuando corresponda. No hay reintentos
periódicos, servicio permanente, watcher ni editor integrado. Desde el incremento 7
se puede reindexar explícitamente o abrir un editor externo. El controlador se usa de forma
secuencial; no compartir una instancia entre varios workers externos.

## Dependencias en Linux local

El núcleo, snapshot y TUI siguen sin dependencias Python externas. GTK requiere
PyGObject y GTK 4 del mismo entorno de Python. Usar el Python de la distribución
para crear el venv; no basta con exponer dist-packages de otra versión de Python.

Debian/Ubuntu, cuando se tiene administración del equipo:

```bash
sudo apt-get update
sudo apt-get install python3-gi python3-venv gir1.2-gtk-4.0 libgtk-4-bin xvfb xauth dbus-x11
/usr/bin/python3 -m venv --system-site-packages .venv
```

Crear el venv así solo si .venv no contiene un entorno que se quiera conservar.
Si ya existe uno basado en el mismo Python del sistema, se puede habilitar
`include-system-site-packages = true` en su pyvenv.cfg. No exponer módulos binarios
de Python 3.13 a un intérprete 3.12.

Arch Linux: las dependencias de ejecución de escritorio son `gtk4` y
`python-gobject`, usando el Python del sistema. El usuario proporcionó estos nombres
como base objetivo; no se ejecutó una instalación ni una prueba sobre Arch aquí.

```bash
sudo pacman -Syu gtk4 python-gobject
/usr/bin/python -m venv --system-site-packages .venv
```

La sincronización y actualización de Arch se muestra explícita; no se ejecuta desde
Trama. Xvfb solo es necesario para pruebas headless, no para una sesión Xfce con
display. Usar GTK 4 del repositorio de la distribución, nunca GTK 3 como sustituto.

## Lanzamiento local

Desde el checkout, con un espacio ya indexado:

```bash
PYTHONPATH=src .venv/bin/python -m trama_core index .demo/espacio
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend gtk --query cafe --select Inicio.md
```

`--backend auto` abre GTK si PyGObject/GTK 4 y un display están disponibles; si no,
usa TUI. No se importa gi para snapshot/TUI. Sin DISPLAY ni WAYLAND_DISPLAY, auto
elige terminal antes de inicializar GTK. Un backend gtk explícito falla con un
mensaje si falta GTK/display; no simula una ventana.

```bash
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend snapshot --query cafe --select Inicio.md
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend tui --query cafe --select Inicio.md
```

Snapshot imprime JSON y termina (código 1 si falló alguna consulta). TUI imprime una
vista textual; con stdin interactivo admite /buscar TEXTO, /abrir UUID|RUTA,
/resultado N, /entrada N, /salida N, /atras, /estado y /salir. Los índices de selección
son desde 0 en la lista mostrada. Con stdin no interactivo imprime una sola vista.
Los controles de terminal en textos de notas se representan sin ejecutarlos.
El incremento 6 añade los comandos de navegación descritos al final.

## Runtime real preparado en este contenedor

Detectado Debian 13, sin sudo ni permisos para modificar /var/lib/apt. APT update
normal falló por permisos; no fue una denegación de la autorización del usuario.
Se descargaron con APT y firmas Debian verificadas, sin instalar globalmente:

- gir1.2-gtk-4.0, libgtk-4-bin, libgtk-4-1, libgtk-4-common: GTK 4.18.6.
- gir1.2-graphene-1.0, libgraphene-1.0-0, libgles2, libcairo-script-interpreter2,
  liblzo2-2: dependencias seleccionadas por APT.
- xvfb: 21.1.16 (paquete Debian de seguridad).

python3-gi 3.50.0, xauth y dbus-x11 ya estaban disponibles en el sistema. Los .deb
se extrajeron con dpkg-deb -x bajo .runtime-gtk/root; los índices y la caché de APT
quedaron en .runtime-gtk/apt, no en /var. La descarga usó --download-only y
Debug::NoLocking=true porque no se ejecutó dpkg y las cachés son locales. No se
desactivó ninguna verificación de firma, hash o TLS.

El venv anterior Python 3.12 se conserva en .venv-py312. Se creó .venv con
`/usr/bin/python3 -m venv --without-pip --system-site-packages .venv` (Python 3.13.5).
No se necesita pip para ejecutar código vía PYTHONPATH. El bin/python del venv tiene
un launcher local ignorado por Git que establece las rutas de bibliotecas y typelibs
extraídas antes de ejecutar bin/python3. No se copian extensiones gi entre versiones.
`.venv-gtk` fue un entorno temporal de diagnóstico y también está ignorado.

Para usar Xvfb y las bibliotecas extraídas en este contenedor:

```bash
. scripts/gtk-env.sh
xvfb-run -a dbus-run-session -- env GTK_A11Y=none GSK_RENDERER=cairo G_DEBUG=fatal-warnings PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend gtk --query cafe --select Inicio.md --smoke-test
```

El helper solo añade rutas si existe .runtime-gtk/root y debe cargarse desde la raíz
del repositorio. Las cachés fontconfig/Mesa se dirigen a .runtime-gtk/cache mediante
XDG_CACHE_HOME; esto evita escrituras en el home de solo lectura. Los archivos del
runtime no se suben a Git. En una máquina con paquetes del sistema instalados no se
necesitan estas rutas ni el launcher local. El entorno instalado por este trabajo
es específico de Debian amd64: no copiar sus binarios a Arch ni a otra arquitectura.

## Prueba gráfica y límites de la evidencia

--smoke-test no es un mock: ejecuta Gtk.Application, presenta la ventana bajo el
display, carga el contrato en un worker, pulsa un botón de resultado real cuando
existe en la búsqueda y comprueba widgets conectados al árbol y mapeados. Compara
textos de título/UUID, resultados, backlinks, enlaces salientes y estado con el
snapshot del controlador. Emite un informe JSON verified=true y cierra ventana,
executor y bucle de GLib. Tiene timeout de 10 segundos. Si no puede inspeccionar
una nota real, falla; no convierte una ejecución TUI en una prueba gráfica.

```bash
. scripts/gtk-env.sh
xvfb-run -a dbus-run-session -- env GTK_A11Y=none GSK_RENDERER=cairo G_DEBUG=fatal-warnings PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

La prueba GTK ejecuta además PYTHONWARNINGS=error, comprueba stderr vacío y compara
bytes de todo el espacio antes/después. GTK_A11Y=none y renderer=cairo se aplican
solo a las pruebas headless para no requerir bus de accesibilidad ni GPU. No se
anula accesibilidad en la ventana normal. Sin display o gi, ese test se marca
omitido con motivo; para verificar todo, usar el comando Xvfb anterior.

La evidencia cubre GTK 4.18.6 real bajo Xvfb en Debian 13, no una sesión manual de
Arch/Xfce, escalado HiDPI o tecnologías de asistencia. La paginación y los atajos se implementaron en el incremento 6 siguiente. La edición
de notas sigue fuera de alcance y falta validación manual en un escritorio físico.


## Incremento 6: teclado y paginación

Los atajos generales están activos **dentro de la ventana**, mediante un
Gtk.EventControllerKey en fase CAPTURE. No se registran atajos del sistema Xfce ni
se modifica su configuración. La caja de texto conserva sus teclas de edición.

| Tecla | Contexto | Acción |
| --- | --- | --- |
| Ctrl+F | Cualquier panel | Foco en búsqueda y selección de todo su texto |
| / | Fuera de un campo editable | Igual que Ctrl+F; en búsqueda se escribe normalmente |
| Abajo / Arriba | Búsqueda o resultados | Selecciona e inspecciona el siguiente/anterior resultado; cruza páginas si hace falta |
| Abajo / Arriba | Backlinks o salientes | Recorre enlaces de esa sección sin abrirlos aún |
| Enter / Enter numérico | Resultados | Inspecciona el resultado enfocado |
| Enter / Enter numérico | Backlinks | Abre la nota fuente del backlink enfocado |
| Enter / Enter numérico | Salientes | Abre destino resuelto; roto/ambiguo/externo muestra aviso y mantiene la nota |
| Enter | Búsqueda | Abre el resultado seleccionado o el primero si no había selección |
| Tab | Cualquier panel | Búsqueda → resultados → backlinks → salientes → avisos → navegación → búsqueda |
| Shift+Tab | Cualquier panel | Recorre esos grupos en orden inverso |
| Izquierda / Derecha | Grupo de navegación | Recorre Atrás, Actualizar y botones de página habilitados |
| Enter / Espacio | Botón de navegación | Activación nativa de GTK |
| Alt+Izquierda | Cualquier panel | Atrás en el historial |
| Backspace | Fuera de un campo editable | Atrás; al editar conserva el borrado normal |
| AvPág / RePág | Resultados | Página siguiente/anterior |
| Ctrl+AvPág / Ctrl+RePág | Cualquier panel | Página siguiente/anterior y foco en resultados |
| Escape | Hay texto en búsqueda | Limpia consulta y vuelve a búsqueda, sin cerrar |
| Escape | Consulta vacía y foco fuera de búsqueda | Vuelve a búsqueda |
| Escape | Consulta vacía y foco en búsqueda | Cierra la ventana |

Al entrar con Tab en una sección se cambia su pestaña y se enfoca su primer enlace
(o el enlace cuyo cursor ya estaba seleccionado); sin enlaces se enfoca el panel.
Los enlaces rotos y ambiguos se pueden recorrer para leer su contexto; Enter nunca
inventa un destino. Las notas elegidas se identifican por UUID. Atrás restaura la
nota previa, pero no modifica la consulta ni cambia a la página de resultados donde
aparecía: si está fuera de la página actual no hay un resultado resaltado.

El texto de búsqueda no se vuelve a seleccionar al refrescar datos. Solo Ctrl+F y
/ piden explícitamente seleccionar todo. El render conserva foco y caret, no destruye
los resultados cuando solo cambia la ficha y mantiene el botón de navegación que
seguía enfocado si aún está habilitado. El resultado activo tiene borde café además
del foco nativo. La navegación de flechas no pasa por el debounce de búsqueda.

### Límites y trabajo pendiente

```bash
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend gtk --query cafe --page-size 50
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend snapshot --query cafe --page-size 10
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend tui --query cafe --page-size 10
```

--page-size acepta enteros 1..100 y se valida antes de arrancar GTK. El indicador
muestra `Mostrando 1–50 de 137 resultados`; botones Página anterior/siguiente se
deshabilitan en los extremos. Una nueva consulta comienza en offset 0. Cambiar de
página selecciona el primer resultado; flechas que cruzan un límite conservan el
orden global y seleccionan el vecino. En los extremos se queda en el último/primer
resultado. Una consulta vacía o sin coincidencias muestra 0–0 y no mueve selección.
La paginación usa el contrato v1 existente: sin cambios de esquema SQLite/manifiesto.

El presentador tiene como máximo una página, historial de 100 entradas y cursores
por sección. GTK crea como máximo page-size botones de resultado y recicla la vista
solo cuando cambia la respuesta de búsqueda. Un único worker procesa las operaciones;
la cola tiene como máximo 16 pendientes más una en ejecución. Búsquedas/focos
consecutivos pendientes se reemplazan por el más reciente; deltas de flechas se
suman y se resuelven en un salto, sin abrir cada nota intermedia de una repetición
rápida. Una cola llena muestra aviso y no acepta otra acción hasta tener espacio.
Las llamadas al contrato permanecen fuera del hilo GTK. Estos son límites de
estructura verificados; no equivalen a una medición de RSS, CPU o latencia.

El incremento 7 siguiente reemplaza la carga completa de enlaces por páginas
independientes solicitadas al contrato, con widgets acotados por sección. Tampoco hay watcher: indexar entre
páginas puede cambiar total y orden, como establece el contrato de lectura.

### Controlador compartido y terminal

Presenter acepta page_size y añade estado `page_size`, `offset`, `result_cursor`,
`link_cursors`, `focus` y `close_requested`. Son campos aditivos de snapshot UI v1,
no cambios de ui_contract v1. Métodos compartidos: select_result, move_result,
change_page, set_focus/cycle_focus, move_link/activate y escape. No consultan SQLite
directamente. El snapshot permite comprobar todo ese estado sin un servidor gráfico.

TUI añade /siguiente, /anterior, /abajo, /arriba, /foco PANEL, /tab, /shift-tab,
/enlace-abajo, /enlace-arriba, /enter y /escape, además de los comandos previos.
Los nombres PANEL son search, results, backlinks, outgoing_links, health, navigation.
El cursor de enlaces no abre documentos hasta /enter. /abajo y /arriba seleccionan
resultados e inspeccionan inmediatamente. Snapshot sigue siendo una salida única;
el historial y las acciones sucesivas se prueban con Presenter o TUI.

### Evidencia de teclado

La suite incluye una prueba GTK real que emite key-pressed en el controlador unido
a una ventana mapeada. Verifica foco, selección de texto, flechas, paginación,
Tab/Shift+Tab, Enter en un backlink, Alt+Izquierda y Escape, con avisos de GTK/Python
tratados como errores. Comprueba además que 200 búsquedas pendientes se agrupan,
que el botón de resultado se conserva al inspeccionar y que refrescar no roba la
selección/caret ni el foco de navegación. Las pruebas comparan todos los bytes del
espacio. Se verificó una colección de 137 notas con páginas 50/50/37 e historial
acotado. No es una prueba de pulsaciones físicas en Arch/Xfce ni de lectores de pantalla.

Para probar en local: abrir con el comando GTK anterior, Ctrl+F y escribir una
palabra; Abajo entra en resultados y otra flecha cambia la ficha. Tab lleva a
backlinks; Enter abre la fuente y Alt+Izquierda vuelve. Continuar con Tab a salientes
y avisos; / vuelve al buscador. Probar AvPág/RePág con una colección que supere el
límite. Escape limpia la consulta y, desde búsqueda vacía, vuelve a cerrar.


## Incremento 7: inspector acotado, recarga y editor externo

Backlinks y salientes tienen páginas independientes, de 50 ocurrencias por defecto,
configurables con --link-page-size 1..100. La cabecera muestra, por ejemplo,
`Mostrando 51–100 de 125 backlinks`, y botones Anterior/Siguiente. No se acumulan
páginas ni se solicitan todos los enlaces para recortarlos en la vista. Hay como
máximo link-page-size botones por sección; cambiar una página no cambia la otra.
Los cursores de flechas cruzan páginas; Enter usa el índice local de la página
visible. Cambiar de nota reinicia ambas páginas; refrescar la misma las conserva
salvo que el total disminuya, en cuyo caso se corrigen al último rango válido.

| Tecla / acción | Resultado |
| --- | --- |
| AvPág / RePág en Backlinks o Salientes | Página siguiente/anterior de esa sección |
| Ctrl+AvPág / Ctrl+RePág | Mantiene la paginación global de resultados |
| Ctrl+R o F5 / Actualizar | Reconsulta status, búsqueda y ficha actual; conserva selección y páginas |
| Ctrl+Shift+R / Reindexar | Solicita index bajo flock EX desde el worker y recarga la vista al terminar |
| Ctrl+O / Abrir editor | Valida y abre el archivo actual con el comando externo configurado |

Son atajos de ventana, no globales del sistema. El grupo de navegación incluye
Atrás, Actualizar, Reindexar, Abrir editor y los botones de páginas de resultados;
Izquierda/Derecha los recorre. Los botones de páginas de enlaces también se pueden
activar con ratón o activación nativa cuando tienen foco; AvPág/RePág es el acceso
directo de teclado dentro de sus paneles.

Actualizar no indexa. El inspector consulta stat y muestra `Archivo modificado en
disco; reindexa para actualizar los enlaces` si cambiaron sus metadatos. missing,
unsafe, unreadable o unknown se muestran también como avisos. Para registros
anteriores sin mtime_ns se necesita una indexación inicial que capture ese dato.
No se leen contenidos desde la ficha; las posiciones siguen siendo las del índice.
No hay watcher ni actualización automática al guardar en otro programa.

Reindexar es una acción explícita de metadatos, no una edición de notas. Se ejecuta
en el mismo worker secuencial, no congela el hilo GTK y devuelve busy si otro proceso
tiene el espacio bloqueado. Los errores por archivo se conservan y se muestran; un
index con archivos omitidos no implica que todos se hayan leído correctamente. El
botón no instala paquetes, no cambia permisos y no aplica resoluciones de conflictos.
Si un archivo cambia durante su lectura, index registra un error por archivo y pide
volver a indexar cuando termine de guardarse; nunca pisa el contenido editado.

### Editor externo seguro

Precedencia: --editor explícito, VISUAL no vacío, EDITOR no vacío, xdg-open. La
cadena de configuración se divide con shlex.split; no se evalúan $, backticks,
variables, tuberías, redirecciones ni metacaracteres. También se admite lista argv
mediante la API Python. El archivo se añade siempre como último argumento absoluto,
sin plantillas de sustitución. El UUID se vuelve a comprobar contra el manifiesto bajo SH antes de lanzar.
La ruta debe estar registrada y activa, ser regular,
existir y permanecer dentro del espacio, sin componentes symlink. Rutas absolutas
como identificador, escapes .., archivos desaparecidos y destinos symlink se rechazan.

Se usa subprocess.Popen(argv, shell=False, close_fds=True, start_new_session=True).
El proceso no hereda el descriptor de flock y un hilo daemon recoge su terminación.
No se espera a que el editor cierre para seguir usando GTK. El mensaje confirma la
solicitud de apertura, no que la aplicación externa haya mostrado ventana o guardado
correctamente. El comando configurado es código elegido por el usuario, nunca por
el contenido de una nota. Elegir un editor gráfico para GTK; uno de terminal puede
necesitar un terminal propio. Trama no escribe notas, pero un editor externo puede
guardarlas por decisión del usuario. Como el resto del proyecto, no garantiza
protección frente a sustituciones maliciosas concurrentes hechas fuera de flock.

```bash
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend gtk --query cafe --link-page-size 50 --editor 'gedit --new-window'
PYTHONPATH=src .venv/bin/python -m trama_core ui .demo/espacio --backend gtk --query cafe --editor 'editor-simulado --new-window' --editor-dry-run
```

La segunda orden no lanza nada por sí sola; al pulsar Ctrl+O muestra el argv sin
crear procesos. gedit es solo un ejemplo si el usuario ya lo tiene instalado: no se
instala ni se supone disponible. Sin --editor se usan las alternativas anteriores.
El modo dry-run usa las mismas validaciones de ruta que la apertura real.

```python
from trama_core.ui import Presenter
p = Presenter('/ruta/al/espacio', editor=['editor-simulado', '--new-window'], editor_dry_run=True)
p.refresh(select='nota.md')
p.open_external()
print(p.snapshot()['external_action'])
```

El controlador guarda link_offsets y link_page_size y expone change_link_page,
refresh/reindex y open_external. index_action y external_action muestran los
resultados estructurados del último comando. En tests, open_document/open_external
aceptan runner inyectado compatible con Popen; nunca hace falta abrir un programa
real. Snapshot sigue sin ejecutar acciones al arrancar. TUI añade /reindexar,
/abrir-editor, /enlaces-siguiente y /enlaces-anterior (estos dos usan el panel fijado
por /foco backlinks o /foco outgoing_links). /estado sigue siendo recarga de lectura.

Prueba nueva bajo Xvfb: nota con 125 backlinks y 125 salientes, widgets 50/50/25,
páginas independientes, modificación simulada del usuario, Ctrl+R (aviso modified),
Ctrl+Shift+R (índice al día) y Ctrl+O dry-run. Se comparan bytes de todos los originales,
salvo el cambio deliberado de la fixture realizado para simular al usuario. No se
mide RSS/CPU ni se afirma compatibilidad de editores externos concretos.
