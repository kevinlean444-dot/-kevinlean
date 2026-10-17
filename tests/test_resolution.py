import json
import shutil
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import test_core
from trama_core.core import index, query
from trama_core.reconciliation import conflicts, resolve


class ResolutionTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write

    def setup_orphan(self, ambiguous=False):
        self.write('nota.md', 'original')
        self.write('source.md', '[historia](nota.md)')
        index(self.root)
        old = next(d['id'] for d in query(self.root, 'graph')['documents'] if d['path'] == 'nota.md')
        (self.root / 'nota.md').rename(self.root / 'copia1.md')
        if ambiguous:
            shutil.copyfile(self.root / 'copia1.md', self.root / 'copia2.md')
        else:
            self.write('copia1.md', 'contenido editado')
        index(self.root)
        graph = query(self.root, 'graph')
        current = next(d['id'] for d in graph['documents'] if d['path'] == 'copia1.md')
        return old, current

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_ambiguous_preview_apply_and_rebuild(self):
        old, current = self.setup_orphan(True)
        self.write('target.md', 'otro destino')
        self.write('copia1.md', '[saliente](target.md)')
        self.write('current-source.md', '[actual](copia1.md)')
        index(self.root)
        other = next(d['id'] for d in query(self.root, 'graph')['documents'] if d['path'] == 'copia2.md')
        snapshot = self.snapshot()
        inspection = conflicts(self.root)
        self.assertEqual(inspection['orphans'][0]['id'], old)
        self.assertEqual(inspection['orphans'][0]['historical_references'], 1)
        self.assertTrue(any(c['id'] == current for c in inspection['orphans'][0]['candidates']))
        preview = resolve(self.root, old, current)
        self.assertFalse(preview['applied'])
        self.assertEqual(preview['retired_id'], current)
        self.assertTrue(preview['conflicts_resolved'])
        self.assertTrue(any(e['needs_update'] == 1 for e in preview['links_added']))
        self.assertEqual(snapshot, self.snapshot())
        result = resolve(self.root, old, 'copia1.md', apply=True)
        self.assertTrue(result['applied'])
        self.assertEqual(preview, result | {'applied': False})
        graph = query(self.root, 'graph')
        self.assertEqual(graph['identity_conflicts'], [])
        docs = {d['path']: d['id'] for d in graph['documents']}
        self.assertEqual(docs['copia1.md'], old)
        self.assertEqual(docs['copia2.md'], other)
        self.assertNotIn(current, {d['id'] for d in graph['documents'] + graph['deleted_documents']})
        self.assertEqual({d['path'] for d in query(self.root, 'backlinks', old)}, {'source.md', 'current-source.md'})
        self.assertTrue(any(e['source'] == old and e['raw'] == 'target.md' for e in graph['links']))
        manifest = json.loads((self.root / '.trama/manifest.json').read_text())
        self.assertNotIn(current, manifest['documents'])
        self.assertEqual(manifest['resolutions'][0]['retired_id'], current)
        for path, data in snapshot.items():
            if not path.startswith('.trama/'):
                self.assertEqual((self.root / path).read_bytes(), data)
        (self.root / '.trama/index.sqlite').unlink()
        index(self.root)
        self.assertEqual(query(self.root, 'graph'), graph)

    def test_edited_already_indexed_and_cli(self):
        old, current = self.setup_orphan()
        before = self.snapshot()
        result = subprocess.run([sys.executable, '-m', 'trama_core', 'resolve', str(self.root), old, current, '--dry-run'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['applied'])
        self.assertEqual(before, self.snapshot())
        result = subprocess.run([sys.executable, '-m', 'trama_core', 'resolve', str(self.root), old, 'copia1.md', '--apply'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(query(self.root, 'backlinks', old)[0]['path'], 'source.md')
        self.assertEqual((self.root / 'copia1.md').read_bytes(), b'contenido editado')
        self.assertEqual(conflicts(self.root), {'orphans': []})

    def test_coexisting_files_rejected_unchanged(self):
        self.write('a.md', 'igual')
        self.write('b.md', 'igual')
        index(self.root)
        docs = query(self.root, 'graph')['documents']
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'coexisten'):
            resolve(self.root, docs[0]['id'], docs[1]['id'], apply=True)
        self.assertEqual(before, self.snapshot())

    def test_missing_outside_symlink_and_canonical_rejected(self):
        old, _ = self.setup_orphan()
        before = self.snapshot()
        for dest in ('missing.md', '../outside.md', str(self.root.parent / 'outside.md')):
            with self.assertRaises(ValueError):
                resolve(self.root, old, dest, apply=True)
        self.assertEqual(before, self.snapshot())
        (self.root / 'link.md').symlink_to(self.root / 'copia1.md')
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            resolve(self.root, old, 'link.md', apply=True)
        self.write('explicit.md', '---\nid: 735a4ab1-e729-4359-ab63-ae3cae348098\n---\n# No absorber')
        index(self.root)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'canónico'):
            resolve(self.root, old, 'explicit.md', apply=True)
        self.assertEqual(before, self.snapshot())

    def test_stale_candidate_rejected(self):
        old, current = self.setup_orphan()
        self.write('copia1.md', 'cambio sin indexar')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'cambió'):
            resolve(self.root, old, current, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_database_build_failure_keeps_original_state(self):
        old, current = self.setup_orphan()
        before = self.snapshot()
        original_connect = sqlite3.connect
        def fail_staging(path, *args, **kwargs):
            if str(path).endswith('index.next.sqlite'):
                raise sqlite3.OperationalError('simulated failure')
            return original_connect(path, *args, **kwargs)
        with patch('trama_core.core.sqlite3.connect', side_effect=fail_staging):
            with self.assertRaises(sqlite3.OperationalError):
                resolve(self.root, old, current, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_interrupted_publication_recovers(self):
        old, current = self.setup_orphan()
        from trama_core.core import recover
        real_replace = Path.replace
        def interrupt_manifest(path, target):
            if path.name == 'manifest.next.json':
                raise OSError('simulated interruption between replacements')
            return real_replace(path, target)
        with patch.object(Path, 'replace', interrupt_manifest):
            with self.assertRaisesRegex(OSError, 'interruption'):
                resolve(self.root, old, current, apply=True)
        self.assertTrue((self.root / '.trama/pending').exists())
        graph = query(self.root, 'graph')
        self.assertFalse((self.root / '.trama/pending').exists())
        self.assertEqual(next(d['id'] for d in graph['documents'] if d['path'] == 'copia1.md'), old)
        manifest = json.loads((self.root / '.trama/manifest.json').read_text())
        self.assertNotIn(current, manifest['documents'])
        self.assertEqual(query(self.root, 'backlinks', old)[0]['path'], 'source.md')
