from threading import Thread
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.views.generic import ListView

from .bot_core import BotCore
from .bots.astro_tg_bot import AstroTgBot
from .bots.sql_tg_bot import SqlTgBot
from .models import Client

ACTIVE_BOTS: dict[str | int, Any] = {}


class BotListView(LoginRequiredMixin, ListView[Client]):

    model = Client
    template_name = "bot_list.html"
    context_object_name = "bot_entries"

    def post(self, request: HttpRequest) -> HttpResponse:
        client_id = request.POST.get("client_id")
        bot_type = request.POST.get("bot_type")
        command = request.POST.get("command")

        if not client_id or not bot_type or not command:
            return HttpResponseBadRequest("Faltan parámetros.")

        try:
            self.object = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return HttpResponseBadRequest("Cliente no encontrado.")

        if command == "start":
            self.start_bot(bot_type)
        elif command == "stop":
            self.stop_bot(bot_type)
        elif command == "status":
            self.is_bot_running(bot_type)
        elif command == "restart":
            self.stop_bot(bot_type)
            self.start_bot(bot_type)
        else:
            return HttpResponseBadRequest("Comando inválido.")

        return HttpResponse("Corriendo" if self.is_bot_running(bot_type) else "Detenido")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        bot_entries = []
        for client in context["object_list"].filter(pk__in=ACTIVE_BOTS.keys()):
            bots_for_client = ACTIVE_BOTS.get(client.pk, {})
            for bot_type in bots_for_client.keys():
                bot_entries.append(
                    {"client": client, "bot_type": bot_type, "is_running": bots_for_client[bot_type]["thread"].is_alive()}
                )

        context["bot_entries"] = bot_entries
        context["bot_types"] = [(1, "astro"), (2, "sql")]

        return context

    def start_bot(self, bot_type: str) -> bool:
        if self.is_bot_running(bot_type):
            return False

        bot_instance: BotCore

        match bot_type:
            case "astro":
                bot_instance = AstroTgBot(self.object)
            case "sql":
                bot_instance = SqlTgBot(self.object)
            case _:
                raise ValueError(f"Tipo de bot desconocido: {bot_type}")

        bot_thread = Thread(target=bot_instance.start, daemon=True)
        bot_thread.start()

        if self.object.pk not in ACTIVE_BOTS:
            ACTIVE_BOTS[self.object.pk] = {}

        ACTIVE_BOTS[self.object.pk][bot_type] = {"bot": bot_instance, "thread": bot_thread}
        return True

    def stop_bot(self, bot_type: str) -> bool:
        active_bot = ACTIVE_BOTS.get(self.object.pk, {}).get(bot_type)
        if active_bot:
            active_bot["bot"].stop()
            ACTIVE_BOTS[self.object.pk].pop(bot_type, None)
            return True
        return False

    def is_bot_running(self, bot_type: str) -> bool:
        thread = ACTIVE_BOTS.get(self.object.pk, {}).get(bot_type, {}).get("thread")
        return thread is not None and thread.is_alive()
