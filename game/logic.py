"""
Правила русских шашек (без Django — чистый Python).

Доска — строка из 64 символов, строка за строкой, сверху вниз:
    '.'  пустая клетка
    'w' / 'W'  белая шашка / белая дамка
    'b' / 'B'  чёрная шашка / чёрная дамка

Белые стоят внизу (строки 5-7) и ходят «вверх» (номер строки уменьшается).
Чёрные стоят вверху (строки 0-2). Играют только на тёмных клетках: (row + col) % 2 == 1.

Правила:
  * обычная шашка ходит вперёд на 1 клетку по диагонали, бьёт и вперёд, и назад;
  * дамка ходит и бьёт на любое расстояние по диагонали;
  * бить обязательно; бить можно любым способом (не обязательно «большинством»),
    но серию взятий нужно закончить;
  * побитые шашки снимаются после окончания хода, одну шашку нельзя бить дважды;
  * шашка, достигшая последней линии, становится дамкой (в том числе в ходе взятия
    — тогда она продолжает бить уже как дамка);
  * проигрывает тот, у кого нет шашек или нет доступных ходов.
"""
import random

SIZE = 8
EMPTY = "."
DIRECTIONS = ((-1, -1), (-1, 1), (1, -1), (1, 1))


# ---------------------------------------------------------------- доска ----
def initial_board() -> str:
    rows = []
    for r in range(SIZE):
        row = ""
        for c in range(SIZE):
            if (r + c) % 2 == 1 and r < 3:
                row += "b"
            elif (r + c) % 2 == 1 and r > 4:
                row += "w"
            else:
                row += EMPTY
        rows.append(row)
    return "".join(rows)


def to_grid(board: str) -> list:
    return [list(board[r * SIZE:(r + 1) * SIZE]) for r in range(SIZE)]


def to_string(grid: list) -> str:
    return "".join("".join(row) for row in grid)


def color_of(piece: str):
    if piece in ("w", "W"):
        return "w"
    if piece in ("b", "B"):
        return "b"
    return None


def opponent(color: str) -> str:
    return "b" if color == "w" else "w"


def inside(r: int, c: int) -> bool:
    return 0 <= r < SIZE and 0 <= c < SIZE


def promotion_row(color: str) -> int:
    return 0 if color == "w" else SIZE - 1


def count_pieces(board: str) -> dict:
    return {
        "w": board.count("w") + board.count("W"),
        "b": board.count("b") + board.count("B"),
    }


# ----------------------------------------------------------------- ходы ----
def _capture_options(grid, color, pos, king, captured):
    """Все возможные одиночные взятия из клетки pos: список (клетка_посадки, жертва)."""
    r, c = pos
    options = []
    for dr, dc in DIRECTIONS:
        if not king:
            mr, mc = r + dr, c + dc
            lr, lc = r + 2 * dr, c + 2 * dc
            if (
                inside(lr, lc)
                and color_of(grid[mr][mc]) == opponent(color)
                and (mr, mc) not in captured
                and grid[lr][lc] == EMPTY
            ):
                options.append(((lr, lc), (mr, mc)))
        else:
            rr, cc = r + dr, c + dc
            while inside(rr, cc) and grid[rr][cc] == EMPTY:
                rr += dr
                cc += dc
            if not inside(rr, cc):
                continue
            victim = (rr, cc)
            if color_of(grid[rr][cc]) != opponent(color) or victim in captured:
                continue  # своя шашка или уже побитая — преграда
            lr, lc = rr + dr, cc + dc
            while inside(lr, lc) and grid[lr][lc] == EMPTY:
                options.append(((lr, lc), victim))
                lr += dr
                lc += dc
    return options


def _capture_sequences(grid, color, pos, king, captured):
    """Рекурсивно строит полные серии взятий. Возвращает [(путь, список_побитых)]."""
    options = _capture_options(grid, color, pos, king, captured)
    if not options:
        return []

    expanded = []
    for landing, victim in options:
        new_captured = captured + [victim]
        new_king = king or landing[0] == promotion_row(color)
        tails = _capture_sequences(grid, color, landing, new_king, new_captured)
        expanded.append((landing, victim, new_captured, tails))

    # Дамка, побив шашку, обязана выбрать такое поле посадки, откуда можно бить дальше
    can_continue = {victim for _, victim, _, tails in expanded if tails}

    results = []
    for landing, victim, new_captured, tails in expanded:
        if tails:
            for path, cap in tails:
                results.append(([landing] + path, cap))
        elif victim not in can_continue:
            results.append(([landing], new_captured))
    return results


def get_moves(board: str, color: str) -> list:
    """
    Список допустимых ходов для цвета color. Каждый ход — словарь:
        {"path": [(r, c), (r, c), ...],  # начальная клетка + все клетки остановок
         "captured": [(r, c), ...]}      # побитые шашки
    Если есть взятие — возвращаются только ходы-взятия.
    """
    grid = to_grid(board)
    captures, simple = [], []

    for r in range(SIZE):
        for c in range(SIZE):
            piece = grid[r][c]
            if color_of(piece) != color:
                continue
            king = piece.isupper()

            grid[r][c] = EMPTY  # ходящая шашка не мешает сама себе
            for path, cap in _capture_sequences(grid, color, (r, c), king, []):
                captures.append({"path": [(r, c)] + path, "captured": cap})
            grid[r][c] = piece

            if captures:
                continue  # простые ходы уже не нужны

            forward = -1 if color == "w" else 1
            for dr, dc in DIRECTIONS:
                if king:
                    rr, cc = r + dr, c + dc
                    while inside(rr, cc) and grid[rr][cc] == EMPTY:
                        simple.append({"path": [(r, c), (rr, cc)], "captured": []})
                        rr += dr
                        cc += dc
                elif dr == forward:
                    rr, cc = r + dr, c + dc
                    if inside(rr, cc) and grid[rr][cc] == EMPTY:
                        simple.append({"path": [(r, c), (rr, cc)], "captured": []})

    return captures if captures else simple


def apply_move(board: str, move: dict) -> str:
    """Применяет ход (словарь из get_moves) и возвращает новую доску."""
    grid = to_grid(board)
    (sr, sc) = move["path"][0]
    (er, ec) = move["path"][-1]
    piece = grid[sr][sc]
    color = color_of(piece)

    grid[sr][sc] = EMPTY
    for (vr, vc) in move["captured"]:
        grid[vr][vc] = EMPTY

    promote = piece.isupper() or any(r == promotion_row(color) for r, _ in move["path"][1:])
    grid[er][ec] = color.upper() if promote else color
    return to_string(grid)


def find_move(board: str, color: str, path):
    """Ищет среди допустимых ходов тот, чей путь совпадает с path (или None)."""
    wanted = [tuple(p) for p in path]
    for move in get_moves(board, color):
        if move["path"] == wanted:
            return move
    return None


def winner_color(board: str, turn: str):
    """Если у игрока, чей ход, нет ходов — побеждает соперник. Иначе None."""
    if not get_moves(board, turn):
        return opponent(turn)
    return None


# ------------------------------------------------------------ компьютер ----
def choose_computer_move(board: str, color: str):
    """Простой ИИ: жадный выбор + оценка ответного удара соперника (глубина 2)."""
    moves = get_moves(board, color)
    if not moves:
        return None

    best_score, best = None, []
    for move in moves:
        new_board = apply_move(board, move)
        reply = get_moves(new_board, opponent(color))
        reply_loss = max((len(m["captured"]) for m in reply), default=0)
        if not reply:
            reply_loss = -100  # соперник остался без ходов — отличный ход

        end_r = move["path"][-1][0]
        promoted = new_board.count(color.upper()) > board.count(color.upper())
        advance = (SIZE - 1 - end_r) if color == "w" else end_r

        score = (
            len(move["captured"]) * 10
            - reply_loss * 8
            + (6 if promoted else 0)
            + advance * 0.3
        )
        if best_score is None or score > best_score + 1e-9:
            best_score, best = score, [move]
        elif abs(score - best_score) <= 1e-9:
            best.append(move)
    return random.choice(best)
