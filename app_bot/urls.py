from django.urls import path

from .views import BotListView

urlpatterns = [
    path("", BotListView.as_view(), name="bots"),
]
