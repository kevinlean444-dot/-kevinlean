import json
import sqlite3
import uuid
import unittest

import test_core
from trama_core.core import index, query


class IdentityTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write
    def note(self, name, identity, body='# Destino\ncontenido'):
        self.write(name, f'---\nid: {identity}\n---\n{body}')

    def test_rename_keeps_backlink_and_rebuild(self):
        identity = str(uuid.uuid4())
        self.note('target.md', identity)
        self.write('source.md', '[nota](target.md)')
        index(self.root)
        (self.root / 'target.md').rename(self.root / 'renamed.md')
        index(self.root)
        self.assertEqual(query(self.root, 'backlinks', identity)[0]['path'], 'source.md')
        self.assertEqual(query(self.root, 'backlinks', 'renamed.md')[0]['path'], 'source.md')
        graph = query(self.root, 'graph')
        self.assertEqual(next(d for d in graph['documents'] if d['id'] == identity)['path'], 'renamed.md')
        (self.root / '.trama/index.sqlite').unlink()
        index(self.root)
        self.assertEqual(query(self.root, 'graph'), graph)

    def test_move_and_content_change(self):
        identity = str(uuid.uuid4())
        self.note('old.md', identity)
        self.write('source.md', '[[Destino]]')
        index(self.root)
        old_hash = next(d['hash'] for d in query(self.root, 'graph')['documents'] if d['id'] == identity)
        (self.root / 'folder').mkdir()
        (self.root / 'old.md').rename(self.root / 'folder/new.md')
        self.note('folder/new.md', identity, '# Título nuevo\notro contenido')
        index(self.root)
        graph = query(self.root, 'graph')
        doc = next(d for d in graph['documents'] if d['id'] == identity)
        self.assertNotEqual(doc['hash'], old_hash)
        self.assertEqual(doc['path'], 'folder/new.md')
        self.assertEqual(query(self.root, 'backlinks', identity)[0]['path'], 'source.md')

    def test_equal_content_distinct_documents(self):
        # Byte-identical imported notes must also remain separate (equal hashes).
        self.write('a.md', '# Igual\ncontenido')
        self.write('b.md', '# Igual\ncontenido')
        index(self.root)
        docs = query(self.root, 'graph')['documents']
        self.assertEqual(docs[0]['hash'], docs[1]['hash'])
        self.assertNotEqual(docs[0]['id'], docs[1]['id'])
        for d in docs:
            self.note(d['path'], d['id'], '# Igual\ncontenido')
        index(self.root)
        self.assertEqual({d['id'] for d in query(self.root, 'graph')['documents']}, {d['id'] for d in docs})

    def test_collision_controlled(self):
        identity = str(uuid.uuid4())
        self.note('a.md', identity)
        self.note('b.md', identity)
        result = index(self.root)
        self.assertEqual(result['documents'], 1)
        self.assertIn('UUID duplicado', result['errors'][0]['error'])
        self.assertEqual(result['errors'][0]['path'], 'b.md')
        manifest = json.loads((self.root / '.trama/manifest.json').read_text())
        self.assertEqual(manifest['documents'][identity]['rel_path'], 'a.md')

    def test_assignment_opt_in_and_idempotent(self):
        self.write('a.md', '---\ntitle: Hola\n---\n# Hola\n')
        original = (self.root / 'a.md').read_bytes()
        index(self.root)
        self.assertEqual((self.root / 'a.md').read_bytes(), original)
        identity = query(self.root, 'graph')['documents'][0]['id']
        index(self.root, assign_ids=True)
        data = (self.root / 'a.md').read_bytes()
        self.assertIn(f'id: {identity}\n'.encode(), data)
        self.assertEqual(uuid.UUID(identity).version, 4)
        index(self.root, assign_ids=True)
        self.assertEqual((self.root / 'a.md').read_bytes(), data)

    def test_deletion_and_restore(self):
        identity = str(uuid.uuid4())
        self.note('a.md', identity)
        self.write('s.md', '[a](a.md)')
        index(self.root)
        (self.root / 'a.md').unlink()
        index(self.root)
        graph = query(self.root, 'graph')
        self.assertEqual(graph['deleted_documents'][0]['id'], identity)
        self.assertEqual(query(self.root, 'backlinks', identity), [])
        self.assertEqual(graph['links'][0]['status'], 'unresolved')
        with sqlite3.connect(self.root / '.trama/index.sqlite') as db:
            self.assertEqual(db.execute('select deleted from docs where id=?', (identity,)).fetchone()[0], 1)
        self.note('restored.md', identity)
        index(self.root)
        self.assertEqual(query(self.root, 'backlinks', identity)[0]['path'], 's.md')

    def test_migrate_v1(self):
        identity = str(uuid.uuid4())
        self.write('a.md', '# Importada')
        state = self.root / '.trama'
        state.mkdir()
        (state / 'manifest.json').write_text(json.dumps({'version': 1, 'paths': {'a.md': identity}}))
        index(self.root)
        self.assertEqual(query(self.root, 'graph')['documents'][0]['id'], identity)
        self.assertEqual(json.loads((state / 'manifest.json').read_text())['version'], 2)

    def test_crlf_existing_id_and_invalid_id(self):
        identity = str(uuid.uuid4())
        original = f'---\r\nid: "{identity}"\r\n---\r\n# Nota\r\n'.encode()
        (self.root / 'a.md').write_bytes(original)
        self.write('bad.md', '---\nid: invalid\n---\n# Mala')
        result = index(self.root, assign_ids=True)
        self.assertEqual(result['documents'], 1)
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual((self.root / 'a.md').read_bytes(), original)
        self.assertEqual(query(self.root, 'graph')['documents'][0]['id'], identity)

    def test_removed_link_is_not_preserved(self):
        identity = str(uuid.uuid4())
        self.note('a.md', identity)
        self.write('s.md', '[a](a.md)')
        index(self.root)
        self.write('s.md', '# Sin enlaces')
        (self.root / 'a.md').rename(self.root / 'b.md')
        index(self.root)
        self.assertEqual(query(self.root, 'backlinks', identity), [])
        manifest = json.loads((self.root / '.trama/manifest.json').read_text())
        self.assertEqual(manifest['bindings'], {})
