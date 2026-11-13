import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import advisor


class PcWarnings(unittest.TestCase):
    def test_laptop_balanced_and_16gb(self):
        w = advisor.pc_warnings({'laptop': True, 'plan': 'Balanced', 'ram_gb': 15.7, 'gpus': []}, de=False)
        self.assertTrue(any('High performance' in x for x in w))
        self.assertTrue(any('16 GB' in x for x in w))

    def test_localized_plan(self):
        w = advisor.pc_warnings({'laptop': True, 'plan': 'Ausbalanciert', 'ram_gb': 32, 'gpus': []}, de=True)
        self.assertEqual(len(w), 1)

    def test_desktop_or_enough_ram_is_quiet(self):
        self.assertEqual(advisor.pc_warnings({'laptop': False, 'plan': 'Balanced', 'ram_gb': 31.7, 'gpus': []}), [])
        self.assertEqual(advisor.pc_warnings({'laptop': True, 'plan': 'Ultimative Leistung', 'ram_gb': 32, 'gpus': []}), [])

    def test_unknown_ram_is_quiet(self):
        self.assertEqual(advisor.pc_warnings({'gpus': []}), [])


class LowEndFixes(unittest.TestCase):
    RX6600 = {'gpus': [('AMD Radeon RX 6600', 8.0), ('Virtual Desktop Monitor', None)], 'cpu_threads': 12, 'cpu_cores': 6,
              'ram_gb': 15.9, 'laptop': False, 'plan': 'Razer Cortex Power Plan'}

    def test_8gb_performance_lower_texture_memory_and_fps_target(self):
        s = advisor.build_preset('performance', self.RX6600)
        self.assertEqual(s['texture_memory'], 1)
        self.assertEqual(s['fps_target'], 3)

    def test_balanced_keeps_texture_memory(self):
        s = advisor.build_preset('balanced', self.RX6600)
        self.assertEqual(s['texture_memory'], 2)
        self.assertNotIn('fps_target', s)

    def test_integrated_gets_no_fps_target(self):
        s = advisor.build_preset('performance', {'gpus': [('Intel(R) UHD Graphics', None)], 'cpu_threads': 8, 'ram_gb': 8})
        self.assertNotIn('fps_target', s)

    def test_virtual_monitor_warning(self):
        w = advisor.pc_warnings(self.RX6600, de=False)
        self.assertTrue(any('Virtual Desktop Monitor' in x for x in w))

    def test_real_cards_are_not_virtual(self):
        w = advisor.pc_warnings({'gpus': [('NVIDIA GeForce RTX 4060 Laptop GPU', 8.0), ('Intel(R) UHD Graphics', None)],
                                 'ram_gb': 32}, de=False)
        self.assertEqual(w, [])


if __name__ == '__main__':
    unittest.main()
