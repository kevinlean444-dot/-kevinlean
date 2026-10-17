# Desarrollo de Trama
Explica decisiones en español. Usa cambios pequeños y verificables.
Python >=3.11, biblioteca estándar, SQLite FTS5. No uses sudo ni instalaciones globales.
Ejecuta `PYTHONPATH=src python -m unittest discover -s tests -v` desde este repositorio.
Los documentos son la fuente de verdad: indexar nunca modifica originales.
Los UUID de notas importadas viven exclusivamente en el manifiesto. No reintroducir --assign-ids.
No añadir GUI, sincronización, servicios ni ISO en este incremento.
Cada tarea cloud ya está aislada: trabaja en el checkout existente sin crear worktrees salvo petición expresa.
