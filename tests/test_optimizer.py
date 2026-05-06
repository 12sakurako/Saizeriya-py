import unittest

from saizeriya.model import MenuItem
from saizeriya.optimizer import optimize


class OptimizerTest(unittest.TestCase):
    def test_best_plan_with_budget(self):
        menu = [
            MenuItem("A", 300, 5.0),
            MenuItem("B", 400, 8.0),
            MenuItem("C", 500, 9.0),
        ]
        plans = optimize(menu, budget=800, top_n=1)
        self.assertEqual(1, len(plans))
        self.assertEqual(800, plans[0].total_price)
        self.assertAlmostEqual(14.0, plans[0].total_score)

    def test_invalid_args(self):
        with self.assertRaises(ValueError):
            optimize([], budget=-1)
        with self.assertRaises(ValueError):
            optimize([], budget=0, top_n=0)


if __name__ == "__main__":
    unittest.main()
