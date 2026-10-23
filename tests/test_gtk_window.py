import importlib.util
import json
import os
import subprocess
import sys
import unittest

import test_core
import test_resolution
import test_ui_contract


@unittest.skipUnless(os.environ.get('DISPLAY') and importlib.util.find_spec('gi'),
                     'GTK real requiere PyGObject y display; ejecutar bajo xvfb-run')
class GTKWindowTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    write = test_core.CoreTests.write
    populated = test_ui_contract.UIContractTests.populated
    snapshot = test_resolution.ResolutionTests.snapshot

    def test_real_gtk_window_search_selection_and_widgets(self):
        self.populated()
        before = self.snapshot()
        environment = dict(os.environ, G_DEBUG='fatal-warnings', PYTHONWARNINGS='error')
        result = subprocess.run([sys.executable, '-m', 'trama_core', 'ui', str(self.root),
                                 '--backend', 'gtk', '--query', 'cafe', '--select', 'new.md', '--smoke-test'],
                                capture_output=True, text=True, env=environment, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        data = json.loads(result.stdout)
        self.assertEqual(data['backend'], 'gtk')
        self.assertEqual(data['gtk_version'][0], 4)
        self.assertTrue(data['verified'])
        self.assertTrue(data['mapped'])
        self.assertEqual(data['title'], 'Documento nuevo')
        self.assertEqual(data['results'], 3)
        self.assertEqual(data['backlinks'], 1)
        self.assertIn('Actualizar enlace', data['backlink_texts'][0])
        self.assertIn('Línea 2:', data['backlink_texts'][0])
        self.assertTrue(any('unresolved' in text for text in data['outgoing_texts']))
        self.assertTrue(any('ambiguous' in text for text in data['outgoing_texts']))
        self.assertIn('6 notas', data['status'])
        self.assertIn('1 por actualizar', data['status'])
        self.assertEqual(before, self.snapshot())
