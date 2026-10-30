from django.contrib import admin

from .models import Game, Move


class MoveInline(admin.TabularInline):
    model = Move
    extra = 0
    can_delete = False
    readonly_fields = ("number", "color", "player", "path", "captured_count")


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("id", "white", "black", "vs_computer", "status", "result", "move_count", "updated_at")
    list_filter = ("status", "vs_computer", "result")
    search_fields = ("white__username", "black__username")
    inlines = [MoveInline]


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("game", "number", "color", "player", "captured_count")
    list_filter = ("color",)
