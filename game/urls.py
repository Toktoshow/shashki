from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.lobby, name="lobby"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("game/new/", views.new_game, name="new_game"),
    path("game/<int:pk>/", views.game_detail, name="game"),
    path("game/<int:pk>/join/", views.join_game, name="join_game"),
    path("game/<int:pk>/cancel/", views.cancel_game, name="cancel_game"),
    path("game/<int:pk>/state/", views.api_state, name="api_state"),
    path("game/<int:pk>/move/", views.api_move, name="api_move"),
    path("game/<int:pk>/resign/", views.api_resign, name="api_resign"),
]
