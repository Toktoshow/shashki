import json
import random

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import logic
from .forms import RegisterForm
from .models import Game, Move

User = get_user_model()

# Ничья: 30 полуходов подряд только дамками и без взятий (по 15 на каждого).
QUIET_PLIES_LIMIT = 30
FILES = "abcdefgh"


# ------------------------------------------------------------ помощники ----
def notation(path, captured_count):
    """[[5,0],[4,1]] -> 'a3-b4'; со взятием — 'a3:c5'."""
    squares = [FILES[c] + str(8 - r) for r, c in path]
    return (":" if captured_count else "-").join(squares)


def finish(game, result, reason):
    game.status = Game.Status.FINISHED
    game.result = result
    game.finish_reason = reason


def commit_move(game, color, user, move):
    """Применяет ход к партии, пишет его в историю и проверяет окончание игры."""
    start_r, start_c = move["path"][0]
    is_man_move = game.board[start_r * logic.SIZE + start_c].islower()

    game.board = logic.apply_move(game.board, move)
    game.move_count += 1
    game.last_move = [list(p) for p in move["path"]]
    game.quiet_plies = 0 if (move["captured"] or is_man_move) else game.quiet_plies + 1
    game.turn = logic.opponent(color)

    Move.objects.create(
        game=game,
        number=game.move_count,
        color=color,
        player=user,
        path=game.last_move,
        captured_count=len(move["captured"]),
    )

    winner = logic.winner_color(game.board, game.turn)
    if winner:
        finish(game, winner, "no_moves")
    elif game.quiet_plies >= QUIET_PLIES_LIMIT:
        finish(game, "d", "draw_rule")
    game.save()


def play_computer_turns(game):
    """Пока очередь компьютера — делаем его ходы."""
    bot = game.computer_color
    while game.status == Game.Status.ACTIVE and game.turn == bot:
        move = logic.choose_computer_move(game.board, bot)
        if move is None:
            break
        commit_move(game, bot, None, move)


def serialize(game, user):
    my_color = game.user_color(user)
    legal = []
    if game.status == Game.Status.ACTIVE and my_color and game.turn == my_color:
        legal = [[list(p) for p in m["path"]] for m in logic.get_moves(game.board, my_color)]

    history = [
        {"n": m.number, "color": m.color, "path": m.path, "text": notation(m.path, m.captured_count)}
        for m in game.moves.all()
    ]
    return {
        "id": game.pk,
        "board": game.board,
        "turn": game.turn,
        "status": game.status,
        "result": game.result,
        "finish_reason": game.finish_reason,
        "move_count": game.move_count,
        "my_color": my_color,
        "white": game.white_name,
        "black": game.black_name,
        "vs_computer": game.vs_computer,
        "legal_moves": legal,
        "last_move": game.last_move,
        "counts": logic.count_pieces(game.board),
        "history": history,
    }


def error(message, status=400):
    return JsonResponse({"error": message}, status=status)


# --------------------------------------------------------- регистрация ----
def register(request):
    if request.user.is_authenticated:
        return redirect("lobby")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Добро пожаловать, {user.get_username()}!")
        return redirect("lobby")
    return render(request, "registration/register.html", {"form": form})


# --------------------------------------------------------------- лобби ----
@login_required
def lobby(request):
    user = request.user
    mine = Q(white=user) | Q(black=user)

    my_games = list(
        Game.objects.filter(mine).exclude(status=Game.Status.FINISHED)
        .select_related("white", "black")
    )
    for g in my_games:
        g.my_turn = g.status == Game.Status.ACTIVE and g.user_color(user) == g.turn

    open_games = (
        Game.objects.filter(status=Game.Status.WAITING, vs_computer=False)
        .exclude(mine).select_related("white", "black")
    )
    finished = (
        Game.objects.filter(mine, status=Game.Status.FINISHED)
        .select_related("white", "black")[:8]
    )
    return render(request, "game/lobby.html", {
        "my_games": my_games,
        "open_games": open_games,
        "finished_games": finished,
    })


@login_required
def leaderboard(request):
    played = (
        Count("games_as_white", filter=Q(games_as_white__status="finished"), distinct=True)
        + Count("games_as_black", filter=Q(games_as_black__status="finished"), distinct=True)
    )
    wins = (
        Count("games_as_white", filter=Q(games_as_white__result="w"), distinct=True)
        + Count("games_as_black", filter=Q(games_as_black__result="b"), distinct=True)
    )
    losses = (
        Count("games_as_white", filter=Q(games_as_white__result="b"), distinct=True)
        + Count("games_as_black", filter=Q(games_as_black__result="w"), distinct=True)
    )
    draws = (
        Count("games_as_white", filter=Q(games_as_white__result="d"), distinct=True)
        + Count("games_as_black", filter=Q(games_as_black__result="d"), distinct=True)
    )
    players = (
        User.objects.annotate(played=played, wins=wins, losses=losses, draws=draws)
        .filter(played__gt=0)
        .order_by("-wins", "losses", "username")[:50]
    )
    return render(request, "game/leaderboard.html", {"players": players})


# ------------------------------------------------------ управление игрой ----
@login_required
@require_POST
def new_game(request):
    mode = request.POST.get("mode")
    color = request.POST.get("color")
    if color not in ("w", "b"):
        color = random.choice(["w", "b"])

    game = Game(vs_computer=(mode == "computer"))
    if color == "w":
        game.white = request.user
    else:
        game.black = request.user
    if game.vs_computer:
        game.status = Game.Status.ACTIVE
    game.save()

    if game.vs_computer:
        play_computer_turns(game)  # если человек играет чёрными — компьютер ходит первым
    return redirect("game", pk=game.pk)


@login_required
@require_POST
def join_game(request, pk):
    with transaction.atomic():
        game = get_object_or_404(Game.objects.select_for_update(), pk=pk)
        if (
            game.status != Game.Status.WAITING
            or game.vs_computer
            or game.user_color(request.user)
        ):
            messages.error(request, "К этой партии уже нельзя присоединиться.")
            return redirect("lobby")
        if game.white_id is None:
            game.white = request.user
        else:
            game.black = request.user
        game.status = Game.Status.ACTIVE
        game.save()
    return redirect("game", pk=game.pk)


@login_required
@require_POST
def cancel_game(request, pk):
    game = get_object_or_404(Game, pk=pk)
    if game.status == Game.Status.WAITING and game.user_color(request.user):
        game.delete()
        messages.success(request, "Приглашение отменено.")
    return redirect("lobby")


@login_required
def game_detail(request, pk):
    game = get_object_or_404(Game.objects.select_related("white", "black"), pk=pk)
    return render(request, "game/game.html", {
        "game": game,
        "my_color": game.user_color(request.user),
    })


# ------------------------------------------------------------------ API ----
@login_required
@require_GET
def api_state(request, pk):
    game = get_object_or_404(Game.objects.select_related("white", "black"), pk=pk)
    return JsonResponse(serialize(game, request.user))


def parse_path(request):
    """Читает из тела запроса путь вида {"path": [[r, c], [r, c], ...]}."""
    try:
        path = json.loads(request.body)["path"]
        valid = (
            isinstance(path, list)
            and 2 <= len(path) <= 40
            and all(
                isinstance(p, list) and len(p) == 2
                and all(isinstance(v, int) and not isinstance(v, bool) for v in p)
                for p in path
            )
        )
        return path if valid else None
    except (ValueError, KeyError, TypeError):
        return None


@login_required
@require_POST
def api_move(request, pk):
    path = parse_path(request)
    if path is None:
        return error("Некорректный запрос.")

    with transaction.atomic():
        game = get_object_or_404(Game.objects.select_for_update(), pk=pk)
        color = game.user_color(request.user)
        if color is None:
            return error("Вы не участвуете в этой партии.", 403)
        if game.status != Game.Status.ACTIVE:
            return error("Партия не идёт.", 409)
        if game.turn != color:
            return error("Сейчас не ваш ход.", 409)

        move = logic.find_move(game.board, color, path)
        if move is None:
            return error("Так ходить нельзя. Помните: бить обязательно.")

        commit_move(game, color, request.user, move)
        if game.vs_computer:
            play_computer_turns(game)

    return JsonResponse(serialize(game, request.user))


@login_required
@require_POST
def api_resign(request, pk):
    with transaction.atomic():
        game = get_object_or_404(Game.objects.select_for_update(), pk=pk)
        color = game.user_color(request.user)
        if color is None:
            return error("Вы не участвуете в этой партии.", 403)
        if game.status != Game.Status.ACTIVE:
            return error("Партия не идёт.", 409)
        finish(game, logic.opponent(color), "resign")
        game.save()
    return JsonResponse(serialize(game, request.user))
