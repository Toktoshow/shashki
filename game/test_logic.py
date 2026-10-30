"""Тесты правил игры. Запуск: python manage.py test   (или: python -m unittest game.test_logic)"""
import random
import unittest

from game import logic


def make_board(pieces):
    grid = [["."] * 8 for _ in range(8)]
    for (r, c), p in pieces.items():
        grid[r][c] = p
    return logic.to_string(grid)


class RulesTests(unittest.TestCase):
    def test_initial_position(self):
        b = logic.initial_board()
        self.assertEqual(logic.count_pieces(b), {"w": 12, "b": 12})
        self.assertEqual(len(logic.get_moves(b, "w")), 7)
        self.assertEqual(len(logic.get_moves(b, "b")), 7)

    def test_capture_is_mandatory(self):
        b = make_board({(5, 2): "w", (4, 3): "b", (7, 0): "w"})
        moves = logic.get_moves(b, "w")
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0]["path"], [(5, 2), (3, 4)])

    def test_man_captures_backwards(self):
        b = make_board({(3, 4): "w", (4, 3): "b"})
        moves = logic.get_moves(b, "w")
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0]["path"][-1], (5, 2))

    def test_multi_jump(self):
        b = make_board({(7, 0): "w", (6, 1): "b", (4, 3): "b"})
        moves = logic.get_moves(b, "w")
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0]["path"], [(7, 0), (5, 2), (3, 4)])
        self.assertEqual(len(moves[0]["captured"]), 2)

    def test_promotion_during_capture(self):
        b = make_board({(2, 3): "w", (1, 2): "b", (1, 4): "b"})
        move = logic.get_moves(b, "w")[0]
        self.assertIn("W", logic.apply_move(b, move))

    def test_king_moves_and_captures_far(self):
        self.assertEqual(len(logic.get_moves(make_board({(7, 0): "W"}), "w")), 7)
        b = make_board({(7, 0): "W", (4, 3): "b"})
        ends = {m["path"][-1] for m in logic.get_moves(b, "w")}
        self.assertEqual(ends, {(3, 4), (2, 5), (1, 6), (0, 7)})

    def test_king_must_continue_capturing(self):
        b = make_board({(7, 0): "W", (5, 2): "b", (3, 2): "b"})
        for m in logic.get_moves(b, "w"):
            self.assertEqual(len(m["captured"]), 2)

    def test_no_moves_means_loss(self):
        b = make_board({(0, 1): "w"})
        self.assertEqual(logic.winner_color(b, "b"), "w")

    def test_find_move_rejects_illegal_path(self):
        b = logic.initial_board()
        self.assertIsNone(logic.find_move(b, "w", [(5, 0), (3, 2)]))
        self.assertIsNotNone(logic.find_move(b, "w", [(5, 0), (4, 1)]))

    def test_computer_games_finish_without_errors(self):
        for seed in range(15):
            random.seed(seed)
            b, turn = logic.initial_board(), "w"
            for _ in range(300):
                if logic.winner_color(b, turn):
                    break
                b = logic.apply_move(b, logic.choose_computer_move(b, turn))
                turn = logic.opponent(turn)
                self.assertEqual(len(b), 64)


if __name__ == "__main__":
    unittest.main()
