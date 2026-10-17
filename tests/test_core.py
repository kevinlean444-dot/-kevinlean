import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from trama_core.core import index, query, MAX_BYTES

REPO = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=REPO)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, text):
        (self.root / name).write_text(text, encoding='utf-8')

    def test_complete_cli_and_rebuild(self):
        shutil.copytree(REPO / 'fixtures', self.root, dirs_exist_ok=True)
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        def cli(*args):
            result = subprocess.run([sys.executable, '-m', 'trama_core', args[0], str(self.root), *args[1:]], capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        self.assertEqual(cli('index')['documents'], 3)
        self.assertEqual(cli('search', 'CAFE')[0]['path'], 'Inicio.md')
        self.assertEqual(cli('backlinks', 'Ideas de estudio.md')[0]['path'], 'Inicio.md')
        graph = cli('graph')
        self.assertEqual(len(graph['links']), 6)
        self.assertEqual({e['status'] for e in graph['links']}, {'resolved', 'unresolved', 'external'})
        cli('index')
        self.assertEqual(cli('graph'), graph)
        (self.root / '.trama/index.sqlite').unlink()
        cli('index')
        self.assertEqual(cli('graph'), graph)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir() if p.is_file()})

    def test_ambiguity_duplicates_unicode(self):
        self.write('a.md', '# Árbol\n[[Duplicado]] [[Ausente]] [espacio](nota%20dos.txt)')
        self.write('b.md', '# Duplicado\nidéntico')
        self.write('c.md', '# Duplicado\nidéntico')
        self.write('nota dos.txt', '漢字 y canción')
        self.assertEqual(index(self.root)['documents'], 4)
        graph = query(self.root, 'graph')
        self.assertEqual(len({d['id'] for d in graph['documents']}), 4)
        ambiguous = next(e for e in graph['links'] if e['status'] == 'ambiguous')
        self.assertEqual(len(ambiguous['candidates']), 2)
        self.assertEqual(query(self.root, 'search', 'cancion')[0]['path'], 'nota dos.txt')
        self.assertEqual(query(self.root, 'search', '漢字')[0]['path'], 'nota dos.txt')
        self.assertEqual(query(self.root, 'backlinks', 'nota dos.txt')[0]['path'], 'a.md')

    def test_empty(self):
        self.assertEqual(index(self.root), {'documents': 0, 'links': 0, 'errors': []})
        self.assertEqual(query(self.root, 'graph')['documents'], [])

    def test_unreadable_external_symlink_and_escape(self):
        outside = REPO / 'README.md'
        (self.root / 'external.md').symlink_to(outside)
        (self.root / 'external-dir').symlink_to(REPO / 'docs', target_is_directory=True)
        self.write('blocked.md', 'secret')
        (self.root / 'blocked.md').chmod(0)
        self.addCleanup(lambda: (self.root / 'blocked.md').chmod(0o600))
        self.write('ok.md', '# Seguro\n[escape](../README.md) [symlink](external.md)')
        import trama_core.core as core
        original = core.read_document
        def guarded(path):
            self.assertTrue(path.is_relative_to(self.root))
            return original(path)
        with patch.object(core, 'read_document', side_effect=guarded):
            result = index(self.root)
        self.assertEqual(result['documents'], 1)
        self.assertEqual(len(result['errors']), 3)
        self.assertTrue(all(e['status'] == 'outside' for e in query(self.root, 'graph')['links']))

    def test_limits_utf8_and_duplicate_uuid(self):
        identity = '735a4ab1-e729-4359-ab63-ae3cae348098'
        for name in ('a.md', 'b.md'):
            self.write(name, f'---\nid: {identity}\n---\n# Nota')
        (self.root / 'bad.txt').write_bytes(b'\xff')
        (self.root / 'large.txt').write_bytes(b'x' * (MAX_BYTES + 1))
        result = index(self.root)
        self.assertEqual(result['documents'], 1)
        self.assertEqual(len(result['errors']), 3)

    def test_state_symlink_rejected(self):
        (self.root / '.trama').symlink_to(REPO / 'docs', target_is_directory=True)
        with self.assertRaises(ValueError):
            index(self.root)

    def test_sql_and_fts_input_is_literal(self):
        self.write('note.md', '# café\nA simple note')
        index(self.root)
        self.assertEqual(query(self.root, 'search', '" OR 1=1 --'), [])
        self.assertEqual(query(self.root, 'backlinks', "' OR 1=1 --"), [])
        self.assertEqual(len(query(self.root, 'graph')['documents']), 1)


if __name__ == '__main__':
    unittest.main()
