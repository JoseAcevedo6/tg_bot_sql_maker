import re

import telebot
from openai import OpenAI

from app_bot.bot_core import BotCore
from app_bot.models import Client, Context, Session, User


class AstroTgBot(BotCore):

    def __init__(self, client: Client):

        super().__init__(client)

        self.open_ai_model = OpenAI(api_key=self.client.openai_api_key)
        self.telegram_bot = telebot.TeleBot(self.telegram_api_key)
        self.telegram_bot.message_handler(content_types=["document", "text"])(self.cmd_start)

    def cmd_start(self, message: telebot.types.Message) -> None:

        self.message = message
        self.question = "ayuda" if not self.message.text else self.message.text.lower()

        if self.client.bot_closed == 1:
            session, created = Session.objects.get_or_create(
                client=self.client,
                chat_id=self.message.chat.id,
                defaults={
                    "last_name": self.message.from_user.last_name,
                    "first_name": self.message.from_user.first_name,
                    "validation": 1,
                    "context": Context.objects.get(pk=1),
                },
            )
            if created:
                self.answer = "Por favor, ingrese su dirección de correo electrónico:"
                return self.send_message()
            else:
                if self.question == "revalidar":
                    session.validation = 1
                    session.save()
                    self.answer = "Por favor, ingrese su dirección de correo electrónico:"
                    return self.send_message()

                client_users = User.objects.filter(client=self.client)
                match session.validation:
                    case 1:  # recibiendo el mail, si existe en la tabla de usuarios pido la contraseña
                        if user := client_users.filter(mail=self.question).first():
                            user.session = session
                            user.save()
                            session.validation = 2
                            session.save()
                            self.answer = (
                                f"Muchas gracias, por favor introduzca la contraseña provista por {self.client.business_name}."
                            )
                            return self.send_message()
                        else:
                            self.answer = (
                                f"Lo siento, esa dirección de correo electrónico no coincide con ninguna de las informadas por {self.client.business_name}.\n"
                                "Por favor introduzca la dirección de correo electrónico."
                            )
                            return self.send_message()
                    case 2:  # solicitando password, si coincide la valido
                        if client_users.filter(session=session, password=self.message.text).exists():
                            session.validation = 3
                            session.save()
                            self.answer = "La identificación ha quedado registrada, en que puedo ayudar?"
                            return self.send_message()
                        else:
                            self.answer = (
                                f"Lo siento, la contraseña ingresada no coincide con la provista por {self.client.business_name}\n"
                                'Por favor ingrese nuevamente la contraseña o conteste "revalidar" para cambiar el mail'
                            )
                            return self.send_message()
                    case 3:  # validado al usuario
                        self.user = client_users.filter(session=session).first()
        else:
            self.user = User.objects.filter(client=self.client, session__chat_id=self.message.chat.id).first()

        if not self.user:
            self.answer = (
                f"Lo siento, no estás autorizado a interactuar con {self.client.business_name}.\n"
                "Por favor contacta al administrador del sistema."
            )
            return self.send_message()

        match self.question:
            case "/estado":
                self.answer = f"Para el mes en curso dispones de {self.user.available_tokens} tokens y llevas {self.user.asked_questions} preguntas realizadas."
                return self.send_message()

            case "/recargar":  # uso de este comando??
                self.client = Client.objects.get(pk=self.client.pk)
                self.answer = "Datos recargados."
                return self.send_message()

            case "ayuda" | "help":
                self.answer = (
                    "Reconozco los comandos:\n"
                    "/estado para conocer los tokens disponibles y las preguntas realizadas.\n"
                    "/recargar para revisar hubo algún cambio en tus datos.\n"
                )
                return self.send_message()

            case x if re.search(r"^\s*(hola|/start)\b", x):
                self.answer = (
                    f"¡Hola! {self.message.from_user.first_name or ''} {self.message.from_user.last_name or ''}\n"
                    "Soy Astrobot 🤖🔭. Pregúntame lo que quieras sobre astronomía."
                )
                return self.send_message()

            case x if match := re.search(r"\bbuen[o|a]?s?\s+(d[ií]as?|tardes?|noches?)\b", x):
                time_of_day = match.group(1)
                self.answer = (
                    "Buenas tardes" if "tarde" in time_of_day else "Buenas noches" if "noche" in time_of_day else "Buen día"
                )
                self.answer += ", ¿haceme una consulta sobre astronomía? 🔭"
                return self.send_message()

            case x if re.search(r"^\bgracias\b[\W_]*$", x) or re.search(r"\bmuchas\s*gracias\b", x):
                self.answer = "De nada!"
                return self.send_message()

            case _:
                self.answer = self.get_openai_response(self.question)

                return self.send_message()
