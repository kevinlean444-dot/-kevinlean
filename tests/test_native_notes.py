import importlib.util
import json
import os
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

import test_core
from trama_core.core import index, MAX_BYTES
from trama_core.locking import space_lock
from trama_core.notes import create_note
from trama_core.ui import Presenter
from trama_core import ui_contract


class NativeNoteTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write

    def state_bytes(self):
        return [(self.root / '.trama' / name).read_bytes() for name in ('manifest.json', 'index.sqlite')]

    def test_cli_native_creation_and_optional_editor_dry_run(self):
        self.write('importada.md', '# Original sin ID\n')
        original = (self.root / 'importada.md').read_bytes()
        result = subprocess.run([sys.executable, '-m', 'trama_core', 'new', str(self.root),
                                 'Café: "ideas"', '--open', '--editor', 'editor-falso --flag',
                                 '--editor-dry-run'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(uuid.UUID(data['uuid']).version, 4)
        self.assertTrue(data['external_action']['dry_run'])
        self.assertEqual(data['external_action']['argv'][:2], ['editor-falso', '--flag'])
        content = (self.root / data['rel_path']).read_text()
        self.assertTrue(content.startswith(f"---\nid: {data['uuid']}\ntitle: "))
        title = content.splitlines()[2].removeprefix('title: ')
        self.assertEqual(json.loads(title), 'Café: "ideas"')
        inspected = ui_contract.inspect_document(self.root, data['uuid'])['data']['document']
        self.assertEqual(inspected['identity_source'], 'frontmatter')
        manifest = json.loads((self.root / '.trama/manifest.json').read_text())
        self.assertTrue(manifest['documents'][data['uuid']]['explicit_id'])
        self.assertIn(data['uuid'], [r['uuid'] for r in ui_contract.search(self.root, 'Café')['data']['results']])
        self.assertEqual((self.root / 'importada.md').read_bytes(), original)
        before = self.state_bytes()
        duplicate = subprocess.run([sys.executable, '-m', 'trama_core', 'new', str(self.root), data['rel_path']], capture_output=True, text=True)
        self.assertEqual(duplicate.returncode, 1)
        self.assertEqual(json.loads(duplicate.stdout)['state'], 'already_exists')
        self.assertEqual((self.root / data['rel_path']).read_text(), content)
        self.assertEqual(before, self.state_bytes())

    def test_controller_selects_native_note_and_keeps_imports_immutable(self):
        self.write('importada.md', '# Importada')
        original = (self.root / 'importada.md').read_bytes()
        index(self.root)
        controller = Presenter(self.root)
        controller.refresh(select='importada.md')
        old = controller.state['selected_uuid']
        (self.root / 'carpeta').mkdir()
        self.assertTrue(controller.create_note('carpeta/Árbol.md'))
        action = controller.state['creation_action']
        self.assertEqual(controller.state['selected_uuid'], action['uuid'])
        self.assertEqual(controller.state['inspection']['data']['document']['identity_source'], 'frontmatter')
        self.assertTrue(controller.back())
        self.assertEqual(controller.state['selected_uuid'], old)
        self.assertEqual((self.root / 'importada.md').read_bytes(), original)
        note = (self.root / action['rel_path']).read_bytes()
        index(self.root)
        self.assertEqual((self.root / action['rel_path']).read_bytes(), note)

    def test_creation_rejects_existing_paths_escape_symlinks_and_busy_space(self):
        self.write('original.md', '# NO CAMBIAR\n')
        index(self.root)
        original = (self.root / 'original.md').read_bytes()
        (self.root / 'link.md').symlink_to(self.root / 'original.md')
        (self.root / 'directorio').symlink_to(self.root.parent, target_is_directory=True)
        (self.root / 'dangling.md').symlink_to(self.root / 'ausente.md')
        before = self.state_bytes()
        for path in ('original.md', 'link.md', 'dangling.md', '../escape.md', str(self.root / 'absoluta.md'),
                     'directorio/escape.md', '.trama/oculta.md', 'faltante/nueva.md', '.', 'a\nb'):
            with self.subTest(path=path):
                self.assertFalse(create_note(self.root, path)['ok'])
                self.assertEqual(self.state_bytes(), before)
        with space_lock(self.root, exclusive=True):
            self.assertEqual(create_note(self.root, 'ocupado')['state'], 'busy')
        self.assertFalse((self.root / 'ocupado.md').exists())
        self.assertEqual((self.root / 'original.md').read_bytes(), original)
        self.assertFalse((self.root / 'ausente.md').exists())

    def test_publication_failure_preserves_new_note_and_is_recoverable(self):
        with patch('trama_core.notes.publish', side_effect=OSError('fallo simulado')):
            action = create_note(self.root, 'Recuperable')
        self.assertFalse(action['ok'])
        self.assertTrue(action['created'])
        original = (self.root / 'Recuperable.md').read_bytes()
        self.assertIn(action['uuid'].encode(), original)
        index(self.root)
        self.assertEqual(ui_contract.inspect_document(self.root, action['uuid'])['data']['document']['identity_source'], 'frontmatter')
        self.assertEqual((self.root / 'Recuperable.md').read_bytes(), original)

    def test_touch_vs_content_hash_and_read_limit(self):
        self.write('nota.md', '# Original')
        index(self.root)
        path = self.root / 'nota.md'
        before = self.state_bytes()
        original = path.read_bytes()
        with patch('trama_core.ui_contract.read_document', side_effect=AssertionError('no releer si stat coincide')):
            self.assertFalse(ui_contract.inspect_document(self.root, 'nota.md')['data']['hash_verified'])
        st = path.stat()
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
        controller = Presenter(self.root)
        controller.refresh(select='nota.md')
        data = controller.state['inspection']['data']
        self.assertEqual(data['disk_state'], dict(state='metadata_only', modified=False))
        self.assertFalse(data['content_modified'])
        self.assertTrue(data['hash_verified'])
        self.assertEqual(before, self.state_bytes())
        self.assertEqual(path.read_bytes(), original)
        path.write_bytes(b'# Editadaa')  # same byte count
        controller.refresh()
        data = controller.state['inspection']['data']
        self.assertTrue(data['content_modified'])
        self.assertTrue(data['hash_verified'])
        self.assertEqual(before, self.state_bytes())
        self.assertEqual(path.read_bytes(), b'# Editadaa')
        path.write_bytes(b'x' * (MAX_BYTES + 1))
        with patch('trama_core.ui_contract.read_document', side_effect=AssertionError('no leer archivo grande')):
            data = ui_contract.inspect_document(self.root, 'nota.md')['data']
        self.assertEqual(data['disk_state']['state'], 'too_large')
        self.assertIsNone(data['content_modified'])
        self.assertFalse(data['hash_verified'])


@unittest.skipUnless(os.environ.get('DISPLAY') and importlib.util.find_spec('gi'), 'GTK real requiere Xvfb')
class GTKNativeNoteTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write

    def test_ctrl_n_dialog_creates_and_selects_native_note(self):
        self.write('importada.md', '# Importada')
        index(self.root)
        original = (self.root / 'importada.md').read_bytes()
        script = r'''
import json, sys, time, uuid
from trama_core.ui.gtk import Gdk, Gio, GLib, Gtk, Window
app = Gtk.Application(application_id='io.trama.NativeTest', flags=Gio.ApplicationFlags.NON_UNIQUE)
assert app.register(None)
w = Window(app, sys.argv[1], select='importada.md')
w.present()
def wait(predicate):
    deadline = time.monotonic() + 10
    while not predicate():
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        assert time.monotonic() < deadline, 'GTK timeout'
        time.sleep(.002)
def settled():
    wait(lambda: w.pending == 0 and w.debounce is None and w.snapshot is not None)
    assert not w.worker_error, w.worker_error
wait(lambda: w.title_label.get_mapped() and w.snapshot is not None)
settled()
assert w.key_controller.emit('key-pressed', Gdk.KEY_n, 0, Gdk.ModifierType.CONTROL_MASK)
wait(lambda: w.creation_dialog is not None and w.creation_entry.get_mapped())
w.creation_entry.set_text('Nueva café')
w.creation_entry.emit('activate')
wait(lambda: w.creation_dialog is None)
settled()
action = w.snapshot['creation_action']
assert action['ok'], action
assert uuid.UUID(action['uuid']).version == 4
assert w.snapshot['selected_uuid'] == action['uuid']
assert w.snapshot['inspection']['data']['document']['identity_source'] == 'frontmatter'
assert w.title_label.get_text() == 'Nueva café'
assert any('Nueva café' in label.get_text() for label in w.result_labels)
# Touch: information, no warning of a content edit.
from pathlib import Path
import os
path = Path(sys.argv[1]) / action['rel_path']
st = path.stat()
os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
assert w.key_controller.emit('key-pressed', Gdk.KEY_r, 0, Gdk.ModifierType.CONTROL_MASK)
settled()
assert w.snapshot['inspection']['data']['content_modified'] is False
assert 'contenido idéntico' in w.metadata_label.get_text()
assert 'modificado en disco' not in w.metadata_label.get_text()
w.close()
app.quit()
print(json.dumps(dict(verified=True)))
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.root)], capture_output=True, text=True,
                                env=dict(os.environ, G_DEBUG='fatal-warnings', PYTHONWARNINGS='error'), timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertTrue(json.loads(result.stdout)['verified'])
        self.assertEqual((self.root / 'importada.md').read_bytes(), original)
