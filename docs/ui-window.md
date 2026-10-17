# Ventana mínima de Trama · incremento 5

Ventana real GTK 4 de solo lectura, más TUI y snapshot. Consume exclusivamente el
[contrato UI v1](ui-contract.md). No indexa automáticamente, no escribe documentos,
no abre URLs, no instala paquetes al arrancar y no necesita cuenta ni privilegios.

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
al UUID previo. Fallar una selección no añade un paso al historial. Se muestran hasta
20 resultados (límite actual del contrato utilizado); todavía no hay paginación visual.

CSS local en ui/style.css: beige #f3eadb, papel #fffaf1, café #35251b y encabezados
#e5d4bc. Amarillo suave identifica Actualizar enlace/busy/recovery_needed; rojo claro
marca enlaces rotos; malva marca ambigüedad. Los estados tienen texto además del
color. Labels usan texto plano, nunca markup de notas ni shell. Fuentes y escalado
los aporta GTK; no se descargan recursos visuales.

`busy` conserva el funcionamiento del bucle gráfico y muestra aviso; Actualizar
reconsulta. `recovery_needed`, index_missing e index_stale se muestran sin ejecutar
una escritura automática: indexar desde CLI cuando corresponda. No hay reintentos
periódicos, servicio permanente, watcher ni editor. El controlador se usa de forma
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
Arch/Xfce, escalado HiDPI o tecnologías de asistencia. Próximo incremento pequeño:
paginación visible de resultados y reintento manual por panel, con una revisión de
teclado/foco en una sesión de escritorio real. La edición de notas sigue fuera de
alcance.
