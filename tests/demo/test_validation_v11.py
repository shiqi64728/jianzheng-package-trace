from __future__ import annotations

import unittest

from scripts.demo.build_competition_validation_v11 import REAL_SCENARIOS


class ValidationV11Tests(unittest.TestCase):
    def test_exact_real_scenario_names(self):
        self.assertEqual(len(REAL_SCENARIOS), 5)
        self.assertIn("REAL-NORMAL", REAL_SCENARIOS)
        self.assertIn("REAL-N1-N2", REAL_SCENARIOS)
        self.assertIn("REAL-N2-N3", REAL_SCENARIOS)
        self.assertIn("REAL-MULTISURFACE", REAL_SCENARIOS)
        self.assertIn("REAL-LIGHTING-VARIATION", REAL_SCENARIOS)


if __name__ == "__main__":
    unittest.main()
