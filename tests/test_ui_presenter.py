import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_core
import test_resolution
import test_ui_contract
from trama_core.core import index
from trama_core.locking import space_lock
from trama_core.ui import Presenter
from trama_core.ui.terminal import render


class PresenterTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write
    populated = test_ui_contract.UIContractTests.populated
    setup_orphan = test_resolution.ResolutionTests.setup_orphan
    snapshot = test_resolution.ResolutionTests.snapshot

    def test_search_selection_navigation_back_and_immutability(self):
        old = self.populated()
        before = self.snapshot()
        controller = Presenter(self.root)
        with patch('trama_core.core.read_document', side_effect=AssertionError('UI must only use contract')):
            controller.refresh(query='cafe', select=old)
            state = controller.snapshot()
            self.assertEqual(state['search']['data']['total'], 3)
            self.assertTrue(state['inspection']['data']['backlinks'][0]['needs_update'])
            self.assertTrue(controller.navigate('backlinks', 0))
            self.assertEqual(controller.state['inspection']['data']['document']['rel_path'], 'source.md')
            self.assertEqual(controller.state['history'], [old])
            self.assertTrue(controller.navigate('outgoing_links', 0))
            self.assertEqual(controller.state['selected_uuid'], old)
            self.assertTrue(controller.back())
            self.assertEqual(controller.state['inspection']['data']['document']['rel_path'], 'source.md')
            self.assertTrue(controller.back())
            self.assertEqual(controller.state['selected_uuid'], old)
            self.assertFalse(controller.back())
            self.assertFalse(controller.navigate('outgoing_links', 1))  # ambiguous, never chooses silently
            self.assertEqual(controller.state['selected_uuid'], old)
        self.assertEqual(before, self.snapshot())
        copied = controller.snapshot()
        copied['history'].append('external mutation')
        self.assertNotIn('external mutation', controller.state['history'])
        self.assertIn('Actualizar enlace', render(controller.snapshot()))

    def test_busy_recovery_and_not_found_without_writes(self):
        self.write('a.md', '# Hola')
        index(self.root)
        controller = Presenter(self.root)
        before = self.snapshot()
        with space_lock(self.root, exclusive=True):
            controller.refresh(query='Hola', select='a.md')
            self.assertEqual(controller.state['status']['state'], 'busy')
            self.assertEqual(controller.state['search']['state'], 'busy')
            self.assertEqual(controller.state['inspection']['state'], 'busy')
        self.assertEqual(before, self.snapshot())
        pending = self.root / '.trama/pending'
        pending.write_text('ready\n')
        before = self.snapshot()
        controller.refresh(query='Hola')
        self.assertEqual(controller.state['status']['state'], 'recovery_needed')
        self.assertEqual(before, self.snapshot())
        pending.unlink()
        controller.refresh(query='Hola', select='a.md')
        selected = controller.state['selected_uuid']
        self.assertFalse(controller.select('missing.md'))
        self.assertEqual(controller.state['inspection']['state'], 'not_found')
        self.assertEqual(controller.state['selected_uuid'], selected)
        self.assertEqual(controller.state['history'], [])

    def test_terminal_snapshot_and_tui_use_same_data(self):
        old = self.populated()
        before = self.snapshot()
        base = [sys.executable, '-m', 'trama_core', 'ui', str(self.root), '--query', 'cafe', '--select', old]
        result = subprocess.run(base + ['--backend', 'snapshot'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        controller = Presenter(self.root)
        self.assertEqual(output, controller.refresh(query='cafe', select=old))
        result = subprocess.run(base + ['--backend', 'tui'], input='', capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Documento nuevo', result.stdout)
        self.assertIn('Actualizar enlace', result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_auto_falls_back_without_display_and_smoke_never_fakes_gtk(self):
        self.write('a.md', '# Hola')
        index(self.root)
        environment = dict(os.environ)
        environment.pop('DISPLAY', None)
        environment.pop('WAYLAND_DISPLAY', None)
        base = [sys.executable, '-m', 'trama_core', 'ui', str(self.root), '--backend', 'auto', '--query', 'Hola']
        result = subprocess.run(base, input='', capture_output=True, text=True, env=environment, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Trama · solo lectura', result.stdout)
        result = subprocess.run(base + ['--smoke-test'], capture_output=True, text=True, env=environment, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('"verified": true', result.stdout)
