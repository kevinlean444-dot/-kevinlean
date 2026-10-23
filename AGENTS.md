# Desarrollo de Trama
Explica decisiones en español. Usa cambios pequeños y verificables.
Python >=3.11, biblioteca estándar, SQLite FTS5. Dependencias gráficas opcionales.
No instalar paquetes del sistema sin autorización explícita del usuario.
Ejecuta `PYTHONPATH=src python -m unittest discover -s tests -v` desde este repositorio.
Los documentos son la fuente de verdad: indexar nunca modifica originales.
Los UUID de notas importadas viven exclusivamente en el manifiesto. No reintroducir --assign-ids.
Incremento 5 autoriza GTK 4 de solo lectura y paquetes de sistema si el contenedor lo permite.
No añadir sincronización, servicios ni ISO. No instalar nada automáticamente al abrir la UI.
Cada tarea cloud ya está aislada: trabaja en el checkout existente sin crear worktrees salvo petición expresa.

Las operaciones públicas deben usar space_lock: EX para escrituras, SH para lecturas.
Nunca eliminar .trama/.lock al liberar el bloqueo. Los frontends usan ui_contract,
no helpers privados, acceso directo a SQLite ni lecturas de notas para enriquecer datos.

Incremento 7: la UI puede reindexar solo por acción explícita (desktop_actions,
con flock), y abrir el editor externo con argv validado, sin shell. Nunca modificar
notas existentes ni lanzar procesos al seleccionar un documento. Las listas de
enlaces del inspector deben solicitar páginas, no cargar el grafo completo.

Incremento 8 autoriza crear notas nativas nuevas por acción explícita, con UUID
en frontmatter, creación exclusiva O_EXCL y bloqueo EX. Nunca sobrescribir archivos.
El inspector puede leer hasta MAX_BYTES para verificar SHA-256 si cambian metadatos.
