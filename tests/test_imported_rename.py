import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import unittest

import test_core
from trama_core.core import index, query


class ImportedRenameTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write

    def manifest(self):
        return json.loads((self.root / '.trama/manifest.json').read_text())

    def test_imported_move_keeps_uuid_bytes_and_backlinks(self):
        self.write('old.md', 'contenido original sin frontmatter')
        self.write('source.md', '[anterior](old.md) [[old]]')
        original = (self.root / 'old.md').read_bytes()
        source = (self.root / 'source.md').read_bytes()
        index(self.root)
        identity = next(d['id'] for d in query(self.root, 'graph')['documents'] if d['path'] == 'old.md')
        (self.root / 'sub').mkdir()
        (self.root / 'old.md').rename(self.root / 'sub/new.md')
        self.assertEqual(index(self.root)['errors'], [])
        record = self.manifest()['documents'][identity]
        self.assertEqual(record['rel_path'], 'sub/new.md')
        self.assertEqual(record['previous_paths'], ['old.md'])
        self.assertEqual((self.root / 'sub/new.md').read_bytes(), original)
        self.assertEqual((self.root / 'source.md').read_bytes(), source)
        self.assertEqual(query(self.root, 'backlinks', identity)[0]['path'], 'source.md')
        with sqlite3.connect(self.root / '.trama/index.sqlite') as db:
            self.assertEqual(db.execute('select path from docs where id=?', (identity,)).fetchone()[0], 'sub/new.md')
        graph = query(self.root, 'graph')
        self.assertTrue(all(e['needs_update'] == 1 for e in graph['links']))
        (self.root / '.trama/index.sqlite').unlink()
        index(self.root)
        self.assertEqual(query(self.root, 'graph'), graph)

    def test_existing_original_plus_copy_never_transfers(self):
        self.write('old.md', '# Igual\ncontenido')
        index(self.root)
        identity = query(self.root, 'graph')['documents'][0]['id']
        shutil.copyfile(self.root / 'old.md', self.root / 'copy.md')
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.glob('*.md')}
        index(self.root)
        docs = {d['path']: d for d in query(self.root, 'graph')['documents']}
        self.assertEqual(docs['old.md']['id'], identity)
        self.assertNotEqual(docs['old.md']['id'], docs['copy.md']['id'])
        self.assertEqual(docs['old.md']['hash'], docs['copy.md']['hash'])
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.glob('*.md')})

    def test_ambiguous_rename_does_not_guess_even_with_same_inode(self):
        self.write('old.md', 'idéntico')
        index(self.root)
        identity = query(self.root, 'graph')['documents'][0]['id']
        (self.root / 'old.md').rename(self.root / 'new1.md')
        shutil.copyfile(self.root / 'new1.md', self.root / 'new2.md')
        result = index(self.root)
        self.assertIn('Renombre ambiguo', result['errors'][0]['error'])
        graph = query(self.root, 'graph')
        self.assertEqual(len(graph['documents']), 2)
        self.assertNotIn(identity, {d['id'] for d in graph['documents']})
        self.assertEqual(graph['deleted_documents'][0]['id'], identity)
        self.assertEqual(graph['identity_conflicts'][0]['candidates'], ['new1.md', 'new2.md'])
        index(self.root)
        self.assertEqual(query(self.root, 'graph'), graph | {'errors': []})
        self.assertEqual((self.root / 'new1.md').read_bytes(), 'idéntico'.encode())
        self.assertEqual((self.root / 'new2.md').read_bytes(), 'idéntico'.encode())

    def test_hash_alone_never_transfers(self):
        self.write('old.md', 'igual')
        index(self.root)
        identity = query(self.root, 'graph')['documents'][0]['id']
        shutil.copyfile(self.root / 'old.md', self.root / 'new.md')
        (self.root / 'old.md').unlink()
        result = index(self.root)
        self.assertIn('Renombre no confirmado', result['errors'][0]['error'])
        self.assertNotEqual(query(self.root, 'graph')['documents'][0]['id'], identity)

    def test_explicit_relocate_with_edited_imported_note_cli(self):
        self.write('old.md', 'original')
        self.write('source.md', '[destino](old.md)')
        index(self.root)
        identity = next(d['id'] for d in query(self.root, 'graph')['documents'] if d['path'] == 'old.md')
        (self.root / 'old.md').rename(self.root / 'new.md')
        self.write('new.md', 'contenido cambiado')
        result = subprocess.run([sys.executable, '-m', 'trama_core', 'index', str(self.root), '--relocate', identity, 'new.md'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest()['documents'][identity]['rel_path'], 'new.md')
        self.assertEqual(query(self.root, 'backlinks', identity)[0]['path'], 'source.md')
        self.assertEqual((self.root / 'new.md').read_bytes(), b'contenido cambiado')

    def test_invalid_relocate_preserves_state(self):
        self.write('old.md', 'original')
        index(self.root)
        identity = query(self.root, 'graph')['documents'][0]['id']
        before = (self.root / '.trama/manifest.json').read_bytes()
        with self.assertRaises(ValueError):
            index(self.root, relocate=(identity, '../outside.md'))
        self.assertEqual((self.root / '.trama/manifest.json').read_bytes(), before)
        self.assertEqual((self.root / 'old.md').read_bytes(), b'original')

    def test_assign_ids_removed_from_cli(self):
        self.write('a.md', 'sin ID')
        result = subprocess.run([sys.executable, '-m', 'trama_core', 'index', str(self.root), '--assign-ids'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.root / 'a.md').read_bytes(), b'sin ID')
        self.assertFalse((self.root / '.trama').exists())
