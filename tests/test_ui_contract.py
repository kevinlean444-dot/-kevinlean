from contextlib import closing
import json
import select
import shutil
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import test_core
import test_resolution
from trama_core.core import index, query
from trama_core.reconciliation import resolve
from trama_core import ui_contract as ui


class UIContractTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write
    setup_orphan = test_resolution.ResolutionTests.setup_orphan
    snapshot = test_resolution.ResolutionTests.snapshot

    def hold_lock(self, exclusive=True):
        script = '''import sys
from trama_core.locking import space_lock
with space_lock(sys.argv[1], exclusive=sys.argv[2] == 'True'):
    print('READY', flush=True)
    sys.stdin.readline()
'''
        process = subprocess.Popen([sys.executable, '-c', script, str(self.root), str(exclusive)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def stop():
            try:
                if process.poll() is not None:
                    process.communicate()
                    return
                process.communicate(input='\n', timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
        self.addCleanup(stop)
        self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'Child failed to acquire lock in time')
        self.assertEqual(process.stdout.readline().strip(), 'READY')
        return process

    def test_exclusive_process_rejects_writers_and_ui(self):
        old, current = self.setup_orphan()
        before = self.snapshot()
        holder = self.hold_lock()
        for args in (['index', str(self.root)], ['resolve', str(self.root), old, current, '--apply']):
            result = subprocess.run([sys.executable, '-m', 'trama_core', *args], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Espacio ocupado', result.stderr)
        result = ui.status(self.root)
        self.assertEqual(result['state'], 'busy')
        self.assertEqual(before, self.snapshot())
        holder.communicate(input='\n', timeout=5)
        self.assertTrue(ui.status(self.root)['ok'])
        index(self.root)  # released lock permits a subsequent writer

    def test_shared_process_allows_read_but_not_write(self):
        self.write('a.md', '# Hola')
        index(self.root)
        holder = self.hold_lock(False)
        self.assertTrue(ui.status(self.root)['ok'])
        with self.assertRaisesRegex(RuntimeError, 'ocupado'):
            index(self.root)
        holder.communicate(input='\n', timeout=5)

    def test_locks_are_independent_between_spaces(self):
        self.write('a.md', 'original')
        index(self.root)
        other = self.root / 'other'
        other.mkdir()
        (other / 'note.md').write_text('otro espacio')
        holder = self.hold_lock()
        index(other)
        self.assertTrue(ui.status(other)['ok'])
        holder.communicate(input='\n', timeout=5)

    def populated(self):
        self.write('old.md', '# Documento\n[roto](missing.md)\n[[Duplicado]]\n')
        self.write('source.md', '# Referencia\n[nota](old.md)\n')
        for name in ('dup1.md', 'dup2.md'):
            self.write(name, '# Duplicado\ncafé información\n')
        self.write('gone.md', '# Tema\nidéntico')
        (self.root / 'invalid.txt').write_bytes(b'\xff')
        index(self.root)
        old = next(d['id'] for d in query(self.root, 'graph')['documents'] if d['path'] == 'old.md')
        (self.root / 'old.md').rename(self.root / 'new.md')
        self.write('new.md', '# Documento nuevo\n[roto](missing.md)\n[[Duplicado]]\ncafé local\n')
        (self.root / 'gone.md').rename(self.root / 'cand1.md')
        shutil.copyfile(self.root / 'cand1.md', self.root / 'cand2.md')
        index(self.root)
        resolve(self.root, old, 'new.md', apply=True)
        return old

    def test_inspector_contains_history_broken_ambiguous_and_positions(self):
        old = self.populated()
        before = self.snapshot()
        with patch('trama_core.core.read_document', side_effect=AssertionError('UI must not read documents')):
            result = ui.inspect_document(self.root, old)
            self.assertEqual(result, ui.inspect_document(self.root, 'new.md'))
        self.assertTrue(result['ok'])
        self.assertEqual(set(result), {'version', 'operation', 'ok', 'state', 'data', 'error'})
        self.assertEqual(result['version'], 1)
        data = result['data']
        self.assertEqual(data['document']['uuid'], old)
        self.assertEqual(data['document']['identity_origin'], 'manifest')
        self.assertEqual(data['document']['backlink_count'], 1)
        self.assertEqual(data['document']['needs_update_count'], 1)
        backlink = data['backlinks'][0]
        self.assertTrue(backlink['needs_update'])
        self.assertEqual(backlink['source']['rel_path'], 'source.md')
        self.assertEqual(backlink['line'], 2)
        self.assertEqual(backlink['context'], '[nota](old.md)')
        links = data['outgoing_links']
        self.assertEqual([e['status'] for e in links], ['unresolved', 'ambiguous'])
        self.assertEqual([e['line'] for e in links], [2, 3])
        self.assertEqual(len(links[1]['candidate_uuids']), 2)
        json.dumps(result, allow_nan=False)
        self.assertEqual(before, self.snapshot())

    def test_status_counts_and_health(self):
        self.populated()
        result = ui.status(self.root)
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['counts'], dict(notes=6, attachments=0, links=3,
            needs_update=1, conflicts=1, errors=1, orphans=1, broken=1, ambiguous=1,
            external=0, outside=0, invalid=0))
        self.assertEqual(len(result['data']['conflicts']), 1)
        self.assertEqual(result['data']['errors'][0]['path'], 'invalid.txt')
        candidate = ui.inspect_document(self.root, 'cand1.md')['data']
        self.assertTrue(candidate['document']['has_conflicts'])
        self.assertEqual(len(candidate['health']['conflicts']), 1)
        invalid = ui.inspect_document(self.root, 'invalid.txt')
        self.assertTrue(invalid['ok'])
        self.assertIsNone(invalid['data']['document'])
        self.assertEqual(invalid['data']['health']['errors'][0]['path'], 'invalid.txt')

    def test_search_relevance_snippets_unicode_pagination_and_flags(self):
        self.populated()
        result = ui.search(self.root, 'cafe', limit=2)
        self.assertTrue(result['ok'])
        data = result['data']
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['next_offset'], 2)
        self.assertEqual(data['results'][0]['rel_path'], 'dup1.md')
        self.assertEqual(data['results'][1]['rel_path'], 'dup2.md')
        self.assertIn('[café]', data['results'][0]['snippet'])
        self.assertLessEqual(data['results'][0]['relevance'], data['results'][1]['relevance'])
        last = ui.search(self.root, 'cafe', offset=2)['data']
        self.assertEqual(last['results'][0]['rel_path'], 'new.md')
        self.assertEqual(last['results'][0]['needs_update_count'], 1)
        self.assertIsNone(last['next_offset'])
        self.assertEqual(ui.search(self.root, '" OR 1=1 --')['data']['total'], 0)
        self.assertEqual(ui.search(self.root, '')['data']['results'], [])
        self.assertEqual(ui.search(self.root, 'cafe', limit=101)['state'], 'invalid_request')

    def test_frontmatter_origin_and_unreadable_registered_document(self):
        self.write('a.md', '---\nid: 735a4ab1-e729-4359-ab63-ae3cae348098\n---\n# Canónico')
        index(self.root)
        self.assertEqual(ui.inspect_document(self.root, 'a.md')['data']['document']['identity_origin'], 'frontmatter')
        original = (self.root / 'a.md').read_bytes()
        (self.root / 'a.md').chmod(0)
        self.addCleanup(lambda: (self.root / 'a.md').chmod(0o600))
        index(self.root)
        response = ui.inspect_document(self.root, 'a.md')
        self.assertTrue(response['ok'])
        self.assertFalse(response['data']['document']['indexed'])
        self.assertEqual(len(response['data']['health']['errors']), 1)
        (self.root / 'a.md').chmod(0o600)
        self.assertEqual((self.root / 'a.md').read_bytes(), original)

    def test_missing_stale_invalid_and_not_found_are_structured(self):
        self.assertEqual(ui.status(self.root)['state'], 'index_missing')
        self.write('a.md', '# Hola')
        index(self.root)
        state = self.root / '.trama'
        manifest_path = state / 'manifest.json'
        original = manifest_path.read_bytes()
        manifest = json.loads(original)
        manifest['extra'] = 'changed outside publication'
        manifest_path.write_text(json.dumps(manifest))
        self.assertEqual(ui.status(self.root)['state'], 'index_stale')
        manifest_path.write_bytes(original)
        self.assertEqual(ui.inspect_document(self.root, 'missing.md')['state'], 'not_found')
        with closing(sqlite3.connect(state / 'index.sqlite')) as db, db:
            db.execute('PRAGMA user_version=3')
        self.assertEqual(ui.status(self.root)['state'], 'index_stale')
        index(self.root)
        manifest_path.write_text('{bad json')
        self.assertEqual(ui.status(self.root)['state'], 'manifest_invalid')
        manifest_path.write_bytes(original)
        (state / 'index.sqlite').write_bytes(b'not SQLite')
        self.assertEqual(ui.status(self.root)['state'], 'index_invalid')
        (state / 'index.sqlite').unlink()
        self.assertEqual(ui.status(self.root)['state'], 'index_missing')
        index(self.root)
        result = subprocess.run([sys.executable, '-m', 'trama_core', 'ui-query', str(self.root), 'inspect', 'missing.md'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, '')
        self.assertEqual(json.loads(result.stdout)['state'], 'not_found')

    def test_ui_reports_recovery_needed_without_mutation(self):
        old, current = self.setup_orphan()
        replace = Path.replace
        def interrupt(path, destination):
            if path.name == 'manifest.next.json':
                raise OSError('interrupted publication')
            return replace(path, destination)
        with patch.object(Path, 'replace', interrupt):
            with self.assertRaises(OSError):
                resolve(self.root, old, current, apply=True)
        before = self.snapshot()
        response = ui.status(self.root)
        self.assertEqual(response['state'], 'recovery_needed')
        self.assertEqual(before, self.snapshot())
        index(self.root)
        self.assertTrue(ui.status(self.root)['ok'])

    def test_lock_symlink_rejected_without_document_mutation(self):
        self.write('a.md', 'original')
        index(self.root)
        (self.root / '.trama/.lock').unlink()
        (self.root / '.trama/.lock').symlink_to(self.root / 'a.md')
        self.assertEqual(ui.status(self.root)['state'], 'workspace_invalid')
        with self.assertRaises(ValueError):
            index(self.root)
        self.assertEqual((self.root / 'a.md').read_bytes(), b'original')
