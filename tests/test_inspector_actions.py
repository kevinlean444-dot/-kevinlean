import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_core
import test_resolution
from trama_core import ui_contract as ui
from trama_core.core import index
from trama_core.desktop_actions import open_document
from trama_core.locking import space_lock
from trama_core.ui import Presenter, link_page_text


class InspectorActionTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write
    snapshot = test_resolution.ResolutionTests.snapshot

    def connected(self):
        self.write('central.md', '# Central\n' + '[destino](destino.md)\n' * 125)
        self.write('destino.md', '# Destino')
        for n in range(125):
            self.write(f'fuente-{n:03}.md', '# Fuente\n[central](central.md)')
        index(self.root)

    def test_contract_and_presenter_bound_both_link_pages(self):
        self.connected()
        before = self.snapshot()
        response = ui.inspect_document(self.root, 'central.md')
        self.assertTrue(response['ok'])
        data = response['data']
        self.assertEqual(len(data['backlinks']), 50)
        self.assertEqual(len(data['outgoing_links']), 50)
        self.assertEqual(data['link_pages']['backlinks']['total'], 125)
        self.assertEqual(data['link_pages']['outgoing_links']['total'], 125)
        self.assertEqual(data['document']['backlink_count'], 125)
        final = ui.inspect_document(self.root, 'central.md', backlinks_offset=100, outgoing_offset=100)['data']
        self.assertEqual(len(final['backlinks']), 25)
        self.assertEqual(len(final['outgoing_links']), 25)
        self.assertIsNone(final['link_pages']['backlinks']['next_offset'])
        self.assertTrue(set(e['position'] for e in data['backlinks']).isdisjoint(e['position'] for e in final['backlinks']))
        for kwargs in (dict(link_limit=101), dict(backlinks_offset=-1), dict(outgoing_offset=True)):
            self.assertEqual(ui.inspect_document(self.root, 'central.md', **kwargs)['state'], 'invalid_request')
        controller = Presenter(self.root)
        controller.refresh(select='central.md')
        self.assertTrue(controller.change_link_page('backlinks', 1))
        self.assertEqual(controller.state['link_offsets']['backlinks'], 50)
        self.assertTrue(controller.change_link_page('backlinks', 1))
        self.assertEqual(link_page_text(controller.state, 'backlinks'), 'Mostrando 101–125 de 125 backlinks')
        self.assertFalse(controller.change_link_page('backlinks', 1))
        self.assertTrue(controller.change_link_page('outgoing_links', 1))
        self.assertEqual(controller.state['link_offsets'], dict(backlinks=100, outgoing_links=50))
        self.assertEqual(before, self.snapshot())
        controller.change_link_page('backlinks', -1)
        controller.state['link_cursors']['backlinks'] = 49
        controller.move_link('backlinks', 1)
        self.assertEqual(controller.state['link_offsets']['backlinks'], 100)
        self.assertEqual(controller.state['link_cursors']['backlinks'], 0)
        self.assertTrue(controller.activate('backlinks'))
        self.assertEqual(controller.state['inspection']['data']['document']['rel_path'], 'fuente-100.md')
        self.assertEqual(before, self.snapshot())
        controller.select('central.md')
        controller.change_link_page('outgoing_links', 1)
        self.write('central.md', '# Central\n[destino](destino.md)')  # user edit shrinks the list
        edited = (self.root / 'central.md').read_bytes()
        controller.reindex()
        self.assertEqual(controller.state['link_offsets']['outgoing_links'], 0)
        self.assertEqual(len(controller.state['inspection']['data']['outgoing_links']), 1)
        self.assertEqual((self.root / 'central.md').read_bytes(), edited)

    def test_modified_reload_and_explicit_reindex_with_lock(self):
        self.write('note.md', '# Original')
        index(self.root)
        controller = Presenter(self.root)
        controller.refresh(select='note.md')
        self.assertEqual(controller.state['inspection']['data']['disk_state']['state'], 'current')
        self.write('note.md', '# Editada por el usuario\nTexto nuevo')
        edited = (self.root / 'note.md').read_bytes()
        before = self.snapshot()
        controller.refresh()
        self.assertEqual(controller.state['inspection']['data']['disk_state'], dict(state='modified', modified=True))
        self.assertEqual(before, self.snapshot())
        with space_lock(self.root, exclusive=True):
            controller.reindex()
            self.assertEqual(controller.state['index_action']['state'], 'busy')
        self.assertEqual(before, self.snapshot())
        controller.reindex()
        self.assertTrue(controller.state['index_action']['ok'])
        self.assertEqual(controller.state['inspection']['data']['disk_state']['state'], 'current')
        self.assertEqual(controller.state['inspection']['data']['document']['title'], 'Editada por el usuario')
        self.assertEqual((self.root / 'note.md').read_bytes(), edited)

    def test_external_editor_argv_dry_run_and_environment(self):
        name = 'nota ; $(touch NO_EJECUTAR).md'
        self.write(name, '# Nota importada')
        index(self.root)
        before = self.snapshot()
        runner = Mock(return_value=SimpleNamespace(wait=lambda: 0))
        result = open_document(self.root, name, command=['editor-falso', '--flag', 'literal; touch archivo'], runner=runner)
        self.assertTrue(result['ok'])
        argv = ['editor-falso', '--flag', 'literal; touch archivo', str(self.root / name)]
        runner.assert_called_once_with(argv, shell=False, close_fds=True, start_new_session=True)
        self.assertFalse((self.root / 'NO_EJECUTAR').exists())
        runner.reset_mock()
        with patch.dict(os.environ, VISUAL='editor-visual --new-window', EDITOR='editor-ignorado'):
            result = open_document(self.root, name, dry_run=True, runner=runner)
            self.assertEqual(result['argv'][:2], ['editor-visual', '--new-window'])
        runner.assert_not_called()
        self.assertEqual(before, self.snapshot())
        controller = Presenter(self.root, editor=['editor-falso'], editor_dry_run=True)
        controller.refresh(select=name)
        self.assertTrue(controller.open_external(runner=runner))
        self.assertTrue(controller.state['external_action']['dry_run'])
        runner.assert_not_called()

    def test_external_editor_rejects_escape_missing_and_symlinks(self):
        self.write('note.md', '# Nota')
        index(self.root)
        runner = Mock()
        for destination in ('../outside.md', str(self.root.parent / 'README.md'), 'missing.md'):
            result = open_document(self.root, destination, command=['fake'], runner=runner)
            self.assertFalse(result['ok'])
        before = (self.root / '.trama/manifest.json').read_bytes()
        (self.root / 'note.md').unlink()
        (self.root / 'note.md').symlink_to(self.root.parent / 'README.md')
        self.assertEqual(ui.inspect_document(self.root, 'note.md')['data']['disk_state']['state'], 'unsafe')
        result = open_document(self.root, 'note.md', command=['fake'], runner=runner)
        self.assertFalse(result['ok'])
        self.assertIn('symlinks', result['error'])
        runner.assert_not_called()
        self.assertEqual((self.root / '.trama/manifest.json').read_bytes(), before)

    def test_file_changed_during_index_is_reported_instead_of_marked_current(self):
        from trama_core.core import read_document
        self.write('note.md', '# Antes')
        def saving_editor(path):
            data = read_document(path)
            path.write_text('# Editado mientras se indexaba')
            return data
        with patch('trama_core.core.read_document', side_effect=saving_editor):
            result = index(self.root)
        self.assertEqual(result['documents'], 0)
        self.assertIn('cambió durante indexación', result['errors'][0]['error'])
        self.assertEqual((self.root / 'note.md').read_text(), '# Editado mientras se indexaba')


@unittest.skipUnless(os.environ.get('DISPLAY') and importlib.util.find_spec('gi'), 'GTK real requiere Xvfb')
class GTKInspectorActionTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write
    connected = InspectorActionTests.connected

    def test_real_gtk_dense_inspector_refresh_reindex_and_editor_dry_run(self):
        self.connected()
        original_docs = {p.name: p.read_bytes() for p in self.root.glob('*.md')}
        script = r'''
import json, sys, time
from pathlib import Path
from trama_core.ui.gtk import Gdk, Gio, GLib, Gtk, Window
app = Gtk.Application(application_id='io.trama.DenseInspectorTest', flags=Gio.ApplicationFlags.NON_UNIQUE)
assert app.register(None)
w = Window(app, sys.argv[1], query='central', select='central.md', page_size=10,
           link_page_size=50, editor=['editor-simulado', '--flag'], editor_dry_run=True)
w.present()
def wait(predicate):
    deadline = time.monotonic() + 10
    while not predicate():
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if time.monotonic() > deadline:
            raise AssertionError('GTK timeout')
        time.sleep(.002)
def settled():
    wait(lambda: w.pending == 0 and w.debounce is None and w.snapshot is not None)
    assert not w.worker_error, w.worker_error
def key(value, mods=Gdk.ModifierType(0)):
    assert w.key_controller.emit('key-pressed', value, 0, mods)
wait(lambda: w.title_label.get_mapped() and w.snapshot is not None)
settled()
assert len(w.backlink_buttons) == 50 and len(w.outgoing_buttons) == 50
assert w.link_controls['backlinks']['count'].get_text() == 'Mostrando 1–50 de 125 backlinks'
w.focus_panel('backlinks')
key(Gdk.KEY_Page_Down)
settled()
assert w.snapshot['link_offsets']['backlinks'] == 50
assert len(w.backlink_buttons) == 50
key(Gdk.KEY_Page_Down)
settled()
assert len(w.backlink_buttons) == 25
assert w.link_controls['backlinks']['count'].get_text() == 'Mostrando 101–125 de 125 backlinks'
assert not w.link_controls['backlinks']['next'].get_sensitive()
w.focus_panel('outgoing_links')
key(Gdk.KEY_Page_Down)
settled()
assert w.snapshot['link_offsets']['outgoing_links'] == 50
assert len(w.outgoing_buttons) == 50
file = Path(sys.argv[1]) / 'central.md'
edited = file.read_bytes() + b'\nCambio del usuario\n'
file.write_bytes(edited)
key(Gdk.KEY_r, Gdk.ModifierType.CONTROL_MASK)
settled()
assert w.snapshot['inspection']['data']['disk_state']['modified']
assert 'modificado en disco' in w.metadata_label.get_text()
assert file.read_bytes() == edited
key(Gdk.KEY_r, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
settled()
assert w.snapshot['index_action']['ok']
assert w.snapshot['inspection']['data']['disk_state']['state'] == 'current'
assert file.read_bytes() == edited
key(Gdk.KEY_o, Gdk.ModifierType.CONTROL_MASK)
settled()
assert w.snapshot['external_action']['dry_run'] and w.snapshot['external_action']['ok']
assert w.snapshot['external_action']['argv'] == ['editor-simulado', '--flag', str(file)]
assert file.read_bytes() == edited
w.close()
app.quit()
print(json.dumps(dict(verified=True, max_backlink_widgets=50, max_outgoing_widgets=50, total=125)))
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.root)], capture_output=True, text=True,
                                env=dict(os.environ, G_DEBUG='fatal-warnings', PYTHONWARNINGS='error'), timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertTrue(json.loads(result.stdout)['verified'])
        for name, original in original_docs.items():
            expected = original + b'\nCambio del usuario\n' if name == 'central.md' else original
            self.assertEqual((self.root / name).read_bytes(), expected)
