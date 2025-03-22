from django.core.management.base import BaseCommand

from app_bot_hibrido.bot_core import ChatBot


class Command(BaseCommand):

    help = "Inicia el bot de Telegram"

    def add_arguments(self, parser):

        parser.add_argument("--client_id", type=int, required=True)

    def handle(self, *args, **kwargs):

        chat_bot = ChatBot(client_id=kwargs['client_id'])
        chat_bot.output_style = (self.stdout, self.style) # for debbuging
        self.stdout.write(self.style.SUCCESS(f'Bot {chat_bot.client.business_name} iniciado.'))
        chat_bot.telegram_bot.infinity_polling()
