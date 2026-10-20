import importlib.util
import json
import os
import subprocess
import sys
import unittest

import test_core
import test_ui_contract
import test_resolution
from trama_core.core import index
from trama_core.ui import FOCUS_ORDER, Presenter, page_text


class KeyboardPresenterTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write
    populated = test_ui_contract.UIContractTests.populated
    snapshot = test_resolution.ResolutionTests.snapshot

    def test_arrows_links_enter_history_and_focus_cycle(self):
        old = self.populated()
        before = self.snapshot()
        presenter = Presenter(self.root, page_size=2)
        presenter.refresh(query='cafe')
        self.assertTrue(presenter.move_result(1))
        first = presenter.state['selected_uuid']
        self.assertEqual(presenter.state['result_cursor'], 0)
        presenter.move_result(1)
        second = presenter.state['selected_uuid']
        self.assertNotEqual(first, second)
        presenter.move_result(1)
        self.assertEqual(presenter.state['selected_uuid'], old)
        self.assertEqual(presenter.state['offset'], 2)
        self.assertEqual(len(presenter.results()), 1)
        presenter.set_focus('backlinks')
        self.assertTrue(presenter.activate())
        self.assertEqual(presenter.state['inspection']['data']['document']['rel_path'], 'source.md')
        self.assertTrue(presenter.back())
        self.assertEqual(presenter.state['selected_uuid'], old)
        presenter.set_focus('outgoing_links')
        self.assertFalse(presenter.activate())
        presenter.move_link('outgoing_links', 1)
        self.assertFalse(presenter.activate())
        self.assertEqual(presenter.state['selected_uuid'], old)
        presenter.set_focus('search')
        for expected in (*FOCUS_ORDER[1:], 'search'):
            presenter.cycle_focus()
            self.assertEqual(presenter.state['focus'], expected)
        presenter.cycle_focus(True)
        self.assertEqual(presenter.state['focus'], 'navigation')
        presenter.escape()
        self.assertEqual(presenter.state['query'], '')
        self.assertEqual(presenter.state['focus'], 'search')
        self.assertFalse(presenter.state['close_requested'])
        presenter.escape()
        self.assertTrue(presenter.state['close_requested'])
        self.assertEqual(before, self.snapshot())

    def test_large_collection_paging_is_bounded_and_history_capped(self):
        for n in range(137):
            self.write(f'note-{n:03}.md', '# Nota\nclave')
        index(self.root)
        before = self.snapshot()
        presenter = Presenter(self.root, page_size=50)
        presenter.refresh(query='clave')
        self.assertEqual(len(presenter.results()), 50)
        self.assertEqual(presenter.state['search']['data']['total'], 137)
        self.assertEqual(page_text(presenter.state), 'Mostrando 1–50 de 137 resultados')
        self.assertFalse(presenter.change_page(-1))
        self.assertTrue(presenter.change_page(1))
        self.assertEqual(len(presenter.results()), 50)
        self.assertTrue(presenter.change_page(1))
        self.assertEqual(len(presenter.results()), 37)
        self.assertEqual(page_text(presenter.state), 'Mostrando 101–137 de 137 resultados')
        self.assertFalse(presenter.change_page(1))
        presenter.search('clave')
        for _ in range(137):
            presenter.move_result(1)
        self.assertEqual(presenter.state['inspection']['data']['document']['rel_path'], 'note-136.md')
        self.assertLessEqual(len(presenter.state['history']), 100)
        self.assertLessEqual(len(presenter.results()), 50)
        presenter.search('no existe')
        self.assertEqual(presenter.state['offset'], 0)
        self.assertEqual(page_text(presenter.state), 'Mostrando 0–0 de 0 resultados')
        self.assertFalse(presenter.move_result(1))
        self.assertEqual(before, self.snapshot())
        for invalid in (0, 101, True):
            with self.assertRaises(ValueError):
                Presenter(self.root, page_size=invalid)

    def test_cli_page_size_snapshot_and_tui(self):
        self.populated()
        command = [sys.executable, '-m', 'trama_core', 'ui', str(self.root), '--query', 'cafe', '--page-size', '2']
        result = subprocess.run(command + ['--backend', 'snapshot'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(result.stdout)
        self.assertEqual(state['page_size'], 2)
        self.assertEqual(len(state['search']['data']['results']), 2)
        result = subprocess.run(command + ['--backend', 'tui'], input='', capture_output=True, text=True, timeout=10)
        self.assertIn('Mostrando 1–2 de 3 resultados', result.stdout)
        result = subprocess.run(command + ['--backend', 'snapshot', '--page-size', '101'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        result = subprocess.run(command + ['--backend', 'gtk', '--page-size', '101'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn('page_size', result.stderr)


@unittest.skipUnless(os.environ.get('DISPLAY') and importlib.util.find_spec('gi'), 'Requiere GTK real bajo Xvfb')
class GTKKeyboardTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write
    populated = test_ui_contract.UIContractTests.populated
    snapshot = test_resolution.ResolutionTests.snapshot

    def test_real_key_controller_focus_paging_links_and_escape(self):
        self.populated()
        before = self.snapshot()
        script = r'''
import json, sys, time
from trama_core.ui.gtk import Gdk, Gio, GLib, Gtk, Window
app = Gtk.Application(application_id='io.trama.KeyboardTest', flags=Gio.ApplicationFlags.NON_UNIQUE)
assert app.register(None)
w = Window(app, sys.argv[1], query='cafe', page_size=2)
w.present()
def wait(predicate):
    deadline = time.monotonic() + 8
    while not predicate():
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if time.monotonic() > deadline:
            raise AssertionError('Timeout waiting for GTK state')
        time.sleep(.002)
def settled():
    wait(lambda: w.pending == 0 and w.debounce is None and w.snapshot is not None)
    assert not w.worker_error, w.worker_error
NONE = Gdk.ModifierType(0)
def key(value, modifiers=NONE):
    return w.key_controller.emit('key-pressed', value, 0, modifiers)
wait(lambda: w.title_label.get_mapped() and w.snapshot is not None)
settled()
for _ in range(200):
    w.submit('search', 'cafe')
assert len(w.jobs) <= 1 and w.pending <= 2, 'repeated searches must be coalesced'
settled()
assert len(w.result_buttons) <= 2
assert w.key_controller.get_widget() == w
assert w.key_controller.get_propagation_phase() == Gtk.PropagationPhase.CAPTURE
assert key(Gdk.KEY_f, Gdk.ModifierType.CONTROL_MASK)
assert w.focus_group() == 'search'
assert tuple(w.search_entry.get_selection_bounds()) == (0,4)
assert not key(Gdk.KEY_slash), 'slash must remain editable in SearchEntry'
settled()
w.search_entry.select_region(4,4)
w.submit('refresh')
settled()
assert not w.search_entry.get_selection_bounds(), 'refresh must not select the editable query again'
original_button = w.result_buttons[0]
assert key(Gdk.KEY_Down)
settled()
assert w.snapshot['result_cursor'] == 0
assert w.focus_group() == 'results'
assert original_button == w.result_buttons[0], 'inspecting must not rebuild the result widgets'
assert key(Gdk.KEY_Down)
settled()
assert w.snapshot['result_cursor'] == 1
assert key(Gdk.KEY_Page_Down)
settled()
assert w.snapshot['offset'] == 2
assert len(w.result_buttons) == 1
assert w.results_count.get_text() == 'Mostrando 3–3 de 3 resultados'
assert not w.next_page.get_sensitive()
historical = w.snapshot['selected_uuid']
assert key(Gdk.KEY_Tab)
settled()
assert w.focus_group() == 'backlinks' and w.notebook.get_current_page() == 0
assert key(Gdk.KEY_Return)
settled()
assert w.snapshot['inspection']['data']['document']['rel_path'] == 'source.md'
assert key(Gdk.KEY_Left, Gdk.ModifierType.ALT_MASK)
settled()
assert w.snapshot['selected_uuid'] == historical
assert key(Gdk.KEY_Tab)
settled()
assert w.focus_group() == 'outgoing_links' and w.notebook.get_current_page() == 1
assert key(Gdk.KEY_Return)
settled()
assert w.snapshot['selected_uuid'] == historical
assert key(Gdk.KEY_Tab)
settled()
assert w.focus_group() == 'health'
assert key(Gdk.KEY_Tab)
settled()
assert w.focus_group() == 'navigation'
assert key(Gdk.KEY_Right)
focused_navigation = w.get_focus()
w.submit('refresh')
settled()
assert w.get_focus() == focused_navigation, 'refresh must retain the selected navigation button'
assert key(Gdk.KEY_slash)
assert w.focus_group() == 'search'
settled()
assert not key(Gdk.KEY_BackSpace), 'editing must retain Backspace'
assert key(Gdk.KEY_ISO_Left_Tab, Gdk.ModifierType.SHIFT_MASK)
settled()
assert w.focus_group() == 'navigation'
assert key(Gdk.KEY_Escape)
settled()
assert w.search_entry.get_text() == '' and w.snapshot['query'] == ''
assert w.focus_group() == 'search'
assert key(Gdk.KEY_Escape)
wait(lambda: w.closed)
app.quit()
print(json.dumps(dict(verified=True, key_controller=True, paging=True, history=True, keyboard_focus=True)))
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.root)], capture_output=True, text=True,
                                env=dict(os.environ, G_DEBUG='fatal-warnings', PYTHONWARNINGS='error'), timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertTrue(json.loads(result.stdout)['verified'])
        self.assertEqual(before, self.snapshot())
