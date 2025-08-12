import csv
import io
import logging
import os
import sys
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

import pymupdf
import telebot
from django.db import close_old_connections, connection
from django.db.utils import OperationalError
from django.utils.text import slugify
from langchain.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError

from app_bot.models import Client, Log, User
from idsa.settings import DEBUG

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

telebot.logger.setLevel(logging.INFO)  # Show bots output in console
if not telebot.logger.hasHandlers():
    telebot_handler = logging.StreamHandler(sys.stdout)
    telebot_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    telebot.logger.addHandler(telebot_handler)

P = ParamSpec("P")
R = TypeVar("R")


def ensure_db_connection(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            # Cierra conexiones muertas y abre una nueva para este hilo
            close_old_connections()
            connection.ensure_connection()
            return func(*args, **kwargs)
        except OperationalError:
            # Si la conexión se perdió durante la ejecución, reintenta una vez
            close_old_connections()
            connection.ensure_connection()
            return func(*args, **kwargs)

    return wrapper


class BotCore:

    def __init__(self, client: Client):

        self.client: Client = client
        self.user: User | None = None
        self.message: telebot.types.Message | None = None
        self.question: str | None = None
        self.answer: str | None = None
        self.context_text: str = ""
        self.source: str = ""
        self.master_chat_id: int = int(os.getenv("MASTER_CHAT_ID", "0"))

        self.telegram_api_key = self.client.telegram_api_key_test if DEBUG else self.client.telegram_api_key_prod
        self.chroma_path = self.client.chromadb_test if DEBUG else self.client.chromadb_prod
        self.prompt = self.client.prompt_test if DEBUG else self.client.prompt_prod
        self.open_ai_model: ChatOpenAI | OpenAI
        self.telegram_bot: telebot.TeleBot

    def clean_file_name(self, file_name: str) -> str:

        file_name = file_name.replace(".", "-s-dot-s-")
        file_name = slugify(file_name)

        return file_name.replace("-s-dot-s-", ".")

    def get_chroma_client(self, add_embedding: bool = False) -> Chroma:
        if not self.message:
            raise ValueError("Message is not set. Cannot determine chat ID for Chroma client.")

        embedding_function = None
        if add_embedding:
            embedding_function = OpenAIEmbeddings(api_key=self.client.openai_api_key)

        return Chroma(persist_directory=f"{self.chroma_path}/{self.message.chat.id}", embedding_function=embedding_function)

    def get_langchain_openai_response(self, prompt: str, question: str, context: str | None = None) -> BaseMessage:
        # only for a langchain.ChatOpenAI instance
        if not isinstance(self.open_ai_model, ChatOpenAI):
            return BaseMessage(content="El modelo de IA no está configurado correctamente.")
        if self.user:
            self.user.asked_questions += 1
            self.user.save()  # Actualizo las preguntas realizadas
            if self.user.asked_questions > 1000:  # Espera una décima segundo más por cada pregunta adicional
                delta = (self.user.asked_questions - 1000) / 10
                time.sleep(delta)

        template = ChatPromptTemplate.from_template(prompt + "Pregunta: {question}\n" + "Contexto: {context}")
        prompt = template.format(question=question, context=context or "No se especificó contexto")

        return self.open_ai_model.invoke(prompt)

    def get_openai_response(self, question: str) -> str:
        # only for a OpenAI instance
        if not isinstance(self.open_ai_model, OpenAI):
            return "El modelo de IA no está configurado correctamente."
        if self.user:
            self.user.asked_questions += 1
            self.user.save()
            if self.user.asked_questions > 1000:
                delta = (self.user.asked_questions - 1000) / 10
                time.sleep(delta)

        response = self.open_ai_model.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un asistente experto en astronomía llamado Astrobot. Responde de forma clara, educativa y amigable.",
                },
                {"role": "user", "content": question},
            ],
            max_tokens=400,
            temperature=0.7,
        )

        return response.choices[0].message.content or "No se obtuvo respuesta de OpenAI."

    def get_sqlalchemy_engine(self) -> Engine | str:

        db_model = self.client.external_db
        if db_model is None:
            return "Este cliente no tiene base de datos externa configurada."

        url = URL.create(**db_model.get_sqlalchemy_params())

        return create_engine(url)

    def process_metadata(self, metadata_list: list[Any]) -> tuple[Any, ...]:

        total_urls, total_documents = 0, 0
        unique_urls, unique_documents = set(), set()
        url_counts: dict[Any, Any] = defaultdict(int)
        document_counts: dict[Any, Any] = defaultdict(int)

        for metadata in metadata_list:
            if "url" in metadata:
                total_urls += 1
                url_counts[metadata["url"]] += 1
                unique_urls.add(metadata["url"])

            if "file_path" in metadata:
                total_documents += 1
                document_counts[metadata["file_path"]] += 1
                unique_documents.add(metadata["file_path"])

        return (
            total_urls,
            total_documents,
            list(unique_urls),
            list(unique_documents),
            len(unique_urls),
            len(unique_documents),
            dict(url_counts),
            dict(document_counts),
        )

    def run_external_query(self, query: str) -> str:

        try:
            engine = self.get_sqlalchemy_engine()

            if isinstance(engine, str):
                return engine  # error message

            with engine.connect() as conn:
                result = conn.execute(text(query))
                columns = result.keys()
                rows = result.fetchall()

                if not rows:
                    return "No se encontraron resultados."

                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(columns)  # Header
                writer.writerows(rows)

                return output.getvalue()

        except SQLAlchemyError as e:
            return f"Error al ejecutar el query: {e}"

    def send_message(self) -> None:

        if not self.message:
            return

        Log.objects.create(
            question=self.question,
            answer=self.answer,
            last_name=self.message.from_user.last_name,
            first_name=self.message.from_user.first_name,
            context=self.context_text,
            client=self.client,
            test=1 if DEBUG else 0,
            source=self.source,
        )
        try:
            logger.info(f"Enviando respuesta al usuario {self.message.from_user.id}: {self.answer}")  # Debugging output
            self.telegram_bot.send_message(self.message.chat.id, self.answer)
            self.answer = None
        except telebot.apihelper.ApiTelegramException as e:
            if e.result.status_code == 429:
                logger.info(f"Rate limit hit: retry after {e.result.json()['parameters']['retry_after']} seconds")
            else:
                raise
        except Exception as e:
            logger.info(f"Error general en cmd_start: {e}")

    def start(self) -> None:
        self.telegram_bot.infinity_polling(timeout=60, long_polling_timeout=60)

    def stop(self) -> None:
        self.telegram_bot.stop_polling()

    def word_counter(self, file: str) -> int:

        with pymupdf.open(file) as doc:
            text = []
            for page in doc:
                text.append(page.get_text("text"))

            full_text = "".join(text)
            full_text = full_text.replace("�", "")
            words = full_text.split()

            return len(words)
