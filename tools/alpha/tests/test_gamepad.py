import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import gamepad


class PickNext(unittest.TestCase):
    # a 2 x 2 grid of buttons, and a wide Play button under it
    boxes = [(0, 0, 100, 40), (200, 0, 300, 40), (0, 100, 100, 140), (200, 100, 300, 140), (0, 200, 300, 260)]

    def test_moves_in_the_grid(self):
        self.assertEqual(gamepad.pick_next(self.boxes, 0, 'right'), 1)
        self.assertEqual(gamepad.pick_next(self.boxes, 0, 'down'), 2)
        self.assertEqual(gamepad.pick_next(self.boxes, 3, 'left'), 2)
        self.assertEqual(gamepad.pick_next(self.boxes, 3, 'up'), 1)

    def test_down_reaches_the_wide_button(self):
        self.assertEqual(gamepad.pick_next(self.boxes, 2, 'down'), 4)
        self.assertEqual(gamepad.pick_next(self.boxes, 3, 'down'), 4)

    def test_edges_have_nothing(self):
        self.assertIsNone(gamepad.pick_next(self.boxes, 0, 'up'))
        self.assertIsNone(gamepad.pick_next(self.boxes, 1, 'right'))

    def test_no_focus_starts_at_the_first(self):
        self.assertEqual(gamepad.pick_next(self.boxes, None, 'down'), 0)
        self.assertIsNone(gamepad.pick_next([], None, 'down'))

    def test_prefers_the_one_in_line(self):
        # straight right but far, or close but well below: the one in line
        boxes = [(0, 0, 50, 50), (400, 0, 450, 50), (120, 150, 170, 200)]
        self.assertEqual(gamepad.pick_next(boxes, 0, 'right'), 1)


if __name__ == '__main__':
    unittest.main()
