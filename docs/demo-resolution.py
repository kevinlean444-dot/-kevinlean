"""Ejemplo reproducible; crea un espacio nuevo y nunca sobrescribe uno existente."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

repo = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--space', default='.demo/espacio/incremento3')
args = parser.parse_args()
space = (repo / args.space).resolve()
if not space.is_relative_to(repo / '.demo'):
    parser.error('El ejemplo solo puede crear espacios dentro de .demo del proyecto')
space.mkdir(parents=True, exist_ok=False)
(space / 'nota.md').write_text('contenido importado\n', encoding='utf-8')
(space / 'referencia.md').write_text('[nota](nota.md)\n', encoding='utf-8')
command = [str(repo / '.venv/bin/python'), '-m', 'trama_core']
environment = dict(os.environ, PYTHONPATH=str(repo / 'src'))


def run(*args):
    cmd = command + [args[0], str(space), *args[1:]]
    print('PYTHONPATH=src ' + shlex.join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=repo, env=environment, capture_output=True, text=True, check=True)
    print(result.stdout, end='')
    return json.loads(result.stdout)


run('index')
graph = run('graph')
old_id = next(d['id'] for d in graph['documents'] if d['path'] == 'nota.md')
(space / 'nota.md').rename(space / 'copia1.md')
shutil.copyfile(space / 'copia1.md', space / 'copia2.md')
before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in space.glob('*.md')}
run('index')
run('conflicts', '--json')
run('resolve', old_id, 'copia1.md', '--preview')
run('resolve', old_id, 'copia1.md', '--apply')
run('backlinks', old_id)
assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in space.glob('*.md')}
print('Documentos intactos; resolución y backlinks verificados.')
