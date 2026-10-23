import importlib.util
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_core
import test_resolution
from trama_core.core import index
from trama_core.reconciliation import resolve
from trama_core import ui_contract as ui
from trama_core.ui import Presenter
from trama_core.ui.terminal import render


class HealthTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write
    setup_orphan = test_resolution.ResolutionTests.setup_orphan
    snapshot = test_resolution.ResolutionTests.snapshot

    def test_resolved_rename_suggests_exact_markdown_replacement(self):
        old, current = self.setup_orphan(True)
        resolve(self.root, old, current, apply=True)
        before = self.snapshot()
        with patch('trama_core.core.read_document', side_effect=AssertionError('no leer documentos')):
            response = ui.health(self.root, category='needs_update')
        self.assertTrue(response['ok'], response)
        self.assertEqual(response['data']['total'], 1)
        issue = response['data']['items'][0]
        self.assertEqual(issue['source']['rel_path'], 'source.md')
        self.assertEqual(issue['line'], 1)
        self.assertEqual(issue['current_link'], '[historia](nota.md)')
        self.assertEqual(issue['suggestions'][0]['replacement'], '[historia](copia1.md)')
        self.assertEqual(issue['suggestions'][0]['target']['uuid'], old)
        self.assertEqual(self.snapshot(), before)

    def test_wiki_unique_rename_and_duplicate_title_use_safe_canonical_paths(self):
        self.write('old.md', '# Antiguo')
        self.write('source.md', '[[Antiguo]]\n[texto](old.md#seccion)')
        index(self.root)
        (self.root / 'old.md').rename(self.root / 'nuevo espacio.md')
        self.write('nuevo espacio.md', '# Actual')
        old = json.loads((self.root / '.trama/manifest.json').read_text())['documents']
        old_id = next(i for i, r in old.items() if r['rel_path'] == 'old.md')
        index(self.root, relocate=(old_id, 'nuevo espacio.md'))
        rows = ui.health(self.root, category='needs_update')['data']['items']
        self.assertEqual([r['line'] for r in rows], [1, 2])
        self.assertEqual(rows[0]['suggestions'][0]['replacement'], '[[Actual]]')
        self.assertEqual(rows[1]['suggestions'][0]['replacement'], '[texto](nuevo%20espacio.md#seccion)')
        self.write('duplicada.md', '# Actual')
        index(self.root)
        rows = ui.health(self.root, category='needs_update')['data']['items']
        self.assertEqual(rows[0]['suggestions'][0]['replacement'], '[nota](nuevo%20espacio.md)')

    def test_categories_exact_occurrences_candidates_determinism_and_immutability(self):
        self.write('a.md', '# Duplicado')
        self.write('b.md', '# Duplicado')
        self.write('source.md', '[falta](ausente.md) [[Duplicado]]\n[[Fantasma]] [[Duplicado]]')
        index(self.root)
        before = self.snapshot()
        response = ui.health(self.root)
        self.assertTrue(response['ok'], response)
        self.assertEqual(response['data']['total'], 4)
        self.assertEqual(response, ui.health(self.root))
        broken = ui.health(self.root, category='broken')['data']['items']
        self.assertEqual([r['current_link'] for r in broken], ['[falta](ausente.md)', '[[Fantasma]]'])
        ambiguous = ui.health(self.root, category='ambiguous')['data']['items']
        self.assertEqual([r['line'] for r in ambiguous], [1, 2])
        for issue in ambiguous:
            self.assertEqual([r['rel_path'] for r in issue['candidates']], ['a.md', 'b.md'])
            self.assertEqual([r['replacement'] for r in issue['suggestions']], ['[nota](a.md)', '[nota](b.md)'])
        self.assertEqual(ui.health(self.root, category='conflicts')['data']['total'], 0)
        for args in (dict(category='invalid'), dict(limit=101), dict(offset=-1), dict(limit=True)):
            self.assertEqual(ui.health(self.root, **args)['state'], 'invalid_request')
        self.assertEqual(self.snapshot(), before)

    def test_conflict_links_to_historical_uuid_and_real_candidates(self):
        old, current = self.setup_orphan(True)
        before = self.snapshot()
        response = ui.health(self.root, category='conflicts')
        self.assertTrue(response['ok'], response)
        self.assertEqual(response['data']['total'], 1)
        issue = response['data']['items'][0]
        self.assertEqual(issue['source']['uuid'], old)
        self.assertIsNone(issue['line'])
        self.assertEqual([r['rel_path'] for r in issue['candidates']], ['copia1.md', 'copia2.md'])
        controller = Presenter(self.root)
        controller.refresh()
        controller.show_health('conflicts')
        self.assertTrue(controller.select_issue(0))
        self.assertEqual(controller.state['selected_uuid'], old)
        self.assertTrue(controller.state['inspection']['data']['document']['deleted'])
        self.assertEqual(self.snapshot(), before)

    def test_pagination_controller_navigation_refresh_and_cli_snapshot_tui(self):
        self.write('source.md', '# Fuente\n' + '[falta](ausente.md)\n' * 125)
        index(self.root)
        before = self.snapshot()
        pages = [ui.health(self.root, category='broken', offset=n)['data'] for n in (0, 50, 100)]
        self.assertEqual([len(p['items']) for p in pages], [50, 50, 25])
        self.assertEqual([p['total'] for p in pages], [125] * 3)
        self.assertEqual(len({r['key'] for p in pages for r in p['items']}), 125)
        controller = Presenter(self.root)
        controller.refresh()
        self.assertTrue(controller.show_health('broken'))
        self.assertTrue(controller.move_result(1))
        self.assertEqual(controller.state['selected_issue']['line'], 2)
        self.assertTrue(controller.move_result(50))
        self.assertEqual(controller.state['health_offset'], 50)
        self.assertEqual(controller.state['selected_issue']['line'], 52)
        self.assertTrue(controller.activate('results'))
        self.assertIn('Línea 52', render(controller.snapshot()))
        self.assertTrue(controller.change_page(1))
        self.assertEqual(controller.state['health_offset'], 100)
        self.assertFalse(controller.change_page(1))
        controller.refresh()
        self.assertEqual(controller.state['health_offset'], 100)
        self.assertEqual(self.snapshot(), before)
        def cli(*args):
            result = subprocess.run([sys.executable, '-m', 'trama_core', *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout
        data = json.loads(cli('ui-query', str(self.root), 'health', '--filter', 'broken', '--limit', '10', '--offset', '120'))['data']
        self.assertEqual(len(data['items']), 5)
        snapshot = json.loads(cli('ui', str(self.root), '--backend', 'snapshot', '--filter', 'broken', '--page-size', '10'))
        self.assertTrue(snapshot['health_view'])
        self.assertEqual(len(snapshot['health_response']['data']['items']), 10)
        self.assertIn('de 125 problemas', cli('ui', str(self.root), '--backend', 'tui', '--health'))
        self.assertEqual(self.snapshot(), before)
        self.write('source.md', '# Fuente sin problemas')
        index(self.root)
        controller.refresh()
        self.assertEqual(controller.state['health_offset'], 0)
        self.assertEqual(controller.issues(), [])


@unittest.skipUnless(os.environ.get('DISPLAY') and importlib.util.find_spec('gi'), 'GTK real requiere Xvfb')
class GTKHealthTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write

    def test_real_gtk_health_filters_keyboard_pages_and_editor_dry_run(self):
        self.write('source.md', '# Fuente\n' + '[falta](ausente.md)\n' * 125)
        index(self.root)
        original = (self.root / 'source.md').read_bytes()
        script = r'''
import json, sys, time
from trama_core.ui.gtk import Gdk, Gio, GLib, Gtk, Window
app = Gtk.Application(application_id='io.trama.HealthTest', flags=Gio.ApplicationFlags.NON_UNIQUE)
assert app.register(None)
w = Window(app, sys.argv[1], editor=['editor-simulado'], editor_dry_run=True)
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
def key(value, mods=Gdk.ModifierType(0)):
    assert w.key_controller.emit('key-pressed', value, 0, mods)
wait(lambda: w.title_label.get_mapped() and w.snapshot is not None)
settled()
key(Gdk.KEY_h, Gdk.ModifierType.CONTROL_MASK)
settled()
assert w.snapshot['health_view']
assert len(w.result_buttons) == 50
assert 'de 125 problemas' in w.results_count.get_text()
# Dropdown filters and the same results navigation use bounded issue pages.
w.view_filter.set_selected(3) # broken
settled()
assert w.snapshot['health_filter'] == 'broken'
key(Gdk.KEY_Down)
settled()
assert w.snapshot['selected_issue']['line'] == 2
key(Gdk.KEY_Return)
settled()
assert 'Línea 2' in w.issue_details.get_text()
assert w.issue_details.get_selectable()
key(Gdk.KEY_Page_Down)
settled()
assert len(w.result_buttons) == 50 and w.snapshot['health_offset'] == 50
key(Gdk.KEY_Page_Down)
settled()
assert len(w.result_buttons) == 25 and w.snapshot['health_offset'] == 100
key(Gdk.KEY_Down)
settled()
assert w.snapshot['selected_issue']['line'] == 102
key(Gdk.KEY_o, Gdk.ModifierType.CONTROL_MASK)
settled()
assert w.snapshot['external_action']['ok'] and w.snapshot['external_action']['dry_run']
key(Gdk.KEY_f, Gdk.ModifierType.CONTROL_MASK)
settled()
assert not w.snapshot['health_view']
w.close()
app.quit()
print(json.dumps(dict(verified=True)))
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.root)], capture_output=True, text=True,
                                env=dict(os.environ, G_DEBUG='fatal-warnings', PYTHONWARNINGS='error'), timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertTrue(json.loads(result.stdout)['verified'])
        smoke = subprocess.run([sys.executable, '-m', 'trama_core', 'ui', str(self.root), '--backend', 'gtk',
                                '--health', '--filter', 'broken', '--smoke-test'], capture_output=True, text=True,
                               env=dict(os.environ, G_DEBUG='fatal-warnings', PYTHONWARNINGS='error'), timeout=30)
        self.assertEqual(smoke.returncode, 0, smoke.stderr)
        self.assertEqual(smoke.stderr, '')
        self.assertTrue(json.loads(smoke.stdout)['verified'])
        self.assertEqual(json.loads(smoke.stdout)['results'], 50)
        self.assertEqual((self.root / 'source.md').read_bytes(), original)
