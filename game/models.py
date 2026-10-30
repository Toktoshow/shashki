from django.conf import settings
from django.db import models

from . import logic


class Game(models.Model):
    """Одна партия. Игроки — пользователи Django (их имена хранятся в таблице auth_user)."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Ожидает соперника"
        ACTIVE = "active", "Идёт игра"
        FINISHED = "finished", "Завершена"

    white = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="games_as_white", verbose_name="Белые",
    )
    black = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="games_as_black", verbose_name="Чёрные",
    )
    vs_computer = models.BooleanField("Против компьютера", default=False)

    board = models.CharField("Доска", max_length=64, default=logic.initial_board)
    turn = models.CharField("Чей ход", max_length=1, default="w")  # 'w' или 'b'
    status = models.CharField(
        "Статус", max_length=10, choices=Status.choices, default=Status.WAITING
    )
    result = models.CharField("Результат", max_length=1, blank=True, default="")  # w / b / d
    finish_reason = models.CharField("Причина окончания", max_length=20, blank=True, default="")

    move_count = models.PositiveIntegerField("Сделано ходов", default=0)
    quiet_plies = models.PositiveIntegerField("Ходов без боя и без простых шашек", default=0)
    last_move = models.JSONField("Последний ход", default=list, blank=True)

    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Партия"
        verbose_name_plural = "Партии"

    def __str__(self):
        return f"Партия №{self.pk}: {self.white_name} — {self.black_name}"

    # --- участники -------------------------------------------------------
    @property
    def computer_color(self):
        """Цвет, за который играет компьютер (если партия против компьютера)."""
        if not self.vs_computer:
            return None
        return "b" if self.white_id else "w"

    def user_color(self, user):
        if not user.is_authenticated:
            return None
        if self.white_id == user.id:
            return "w"
        if self.black_id == user.id:
            return "b"
        return None

    def player_name(self, color):
        user = self.white if color == "w" else self.black
        if user is not None:
            return user.get_username()
        if self.vs_computer and color == self.computer_color:
            return "Компьютер"
        if self.status == self.Status.WAITING:
            return "ждём игрока…"
        return "удалённый игрок"

    @property
    def white_name(self):
        return self.player_name("w")

    @property
    def black_name(self):
        return self.player_name("b")

    @property
    def result_label(self):
        return {"w": "Победили белые", "b": "Победили чёрные", "d": "Ничья"}.get(self.result, "")


class Move(models.Model):
    """История ходов партии."""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="moves")
    number = models.PositiveIntegerField("№ хода")
    color = models.CharField("Цвет", max_length=1)
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+", verbose_name="Игрок",
    )  # NULL — ход сделал компьютер
    path = models.JSONField("Путь шашки")
    captured_count = models.PositiveSmallIntegerField("Побито шашек", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]
        verbose_name = "Ход"
        verbose_name_plural = "Ходы"

    def __str__(self):
        return f"{self.game_id}/{self.number}"
