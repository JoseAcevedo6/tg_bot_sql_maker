import ast
import os
import re
from typing import cast

import telebot
from langchain_community.document_loaders import DirectoryLoader, UnstructuredFileLoader, pdf
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app_bot.models import Client, Context, Session, User

from .bot_core import BotCore


class SqlTgBot(BotCore):

    telegram_bot: telebot.TeleBot

    def __init__(self, client: Client):

        super().__init__(client)

        self.open_ai_model = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, api_key=self.client.openai_api_key)
        self.telegram_bot = telebot.TeleBot(self.telegram_api_key)
        if not self.telegram_bot:
            raise RuntimeError("Error al inicializar el bot de Telegram")
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

        if self.message.document:  # reviso si vino un documento
            directory_path = os.path.join(self.client.documents_folder, str(self.message.chat.id))
            os.makedirs(directory_path, exist_ok=True)
            os.makedirs(os.path.join(directory_path, "entrenados"), exist_ok=True)

            file_info = self.telegram_bot.get_file(message.document.file_id)
            downloaded_file = self.telegram_bot.download_file(file_info.file_path)
            file_name = self.clean_file_name(self.message.document.file_name)
            with open(os.path.join(directory_path, file_name), "wb") as new_file:
                new_file.write(downloaded_file)

            self.answer = "Documento descargado exitosamente."
            return self.send_message()

        match self.question:
            case "/estado":
                if self.user:
                    self.answer = f"Para el mes en curso dispones de {self.user.available_tokens} tokens y llevas {self.user.asked_questions} preguntas realizadas."
                else:
                    self.answer = "Bot abierto. Puedes hacer preguntas sobre tu base de datos."
                return self.send_message()

            case "/recargar":  # uso de este comando??
                self.client = Client.objects.get(pk=self.client.pk)
                self.answer = "Datos recargados."
                return self.send_message()

            case "/entrenar":
                # entrena todos los documentos que encuentre en la carpeta y los mueve a la carpeta de entrenados
                folder_path = os.path.join(self.client.documents_folder, str(self.message.chat.id))
                loader = DirectoryLoader(
                    folder_path, glob="*.pdf", loader_cls=cast(type[UnstructuredFileLoader], pdf.PyMuPDFLoader)
                )
                documents = loader.load()

                # Mido si tengo Tokens disponibles para entrenar
                total_palabras = 0
                for d in documents:
                    file = d.metadata["file_path"]
                    total_palabras = total_palabras + self.word_counter(file)

                if self.user and total_palabras > self.user.available_tokens:
                    self.answer = (
                        f"Los documentos que trata de entrenar suman: {total_palabras} tokens"
                        f"Dispone sólo de: {self.user.available_tokens} tokens"
                        "Espere al próximo período o considere el upgrade a una suscripción premium."
                    )
                else:
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=self.client.chunk_size,
                        chunk_overlap=self.client.chunk_overlap,
                        separators=["\n\n", "\n", ".", " ", ""],  # importancia de esto!!
                        length_function=len,
                        add_start_index=True,
                    )

                    os.system(f"mv {folder_path}/*.pdf {folder_path}/entrenados")
                    for d in documents:
                        original_file_path = d.metadata["file_path"]
                        new_file_path = os.path.join(folder_path, "entrenados", os.path.basename(original_file_path))
                        d.metadata["file_path"] = new_file_path

                    if chunks := text_splitter.split_documents(documents):
                        self.answer = (
                            "Entrenando documentos\n"
                            f'Separamos {len(documents)} {"documento" if len(documents) == 1 else "documentos"} en {len(chunks)} chunks.\n'
                        )

                        self.get_chroma_client(add_embedding=True).add_documents(chunks)
                        self.answer += f"Grabados {len(chunks)} a {self.chroma_path}\n"

                        # actualizo los TokensDisponibles
                        if self.user:
                            self.user.available_tokens = self.user.available_tokens - total_palabras
                            self.user.save()

                            self.answer += f"Le quedan {self.user.available_tokens} tokens"
                    else:
                        self.answer = "No hay documentos para entrenar"
                return self.send_message()

            case "/lista":  # lista de materiales entrenados precedidos por un número
                chroma_collection_data = self.get_chroma_client().get()
                metadatas = chroma_collection_data.get("metadatas")
                uris = chroma_collection_data.get("uris")
                data = chroma_collection_data.get("data")

                self.answer = (
                    "Lista de documentos entrenados:\n"
                    f'Longitud de ids: {len(chroma_collection_data.get("ids", []))}\n'
                    f'Longitud de documents: {len(chroma_collection_data.get("documents", []))}\n'
                )

                if uris:
                    self.answer += f"Longitud de urls: {len(uris)}\n"
                if data:
                    self.answer += f"Longitud de data: {len(data)}\n"
                if metadatas:
                    (
                        total_urls,
                        total_documents,
                        unique_urls,
                        unique_documents,
                        num_unique_urls,
                        num_unique_documents,
                        url_counts,
                        document_counts,
                    ) = self.process_metadata(metadatas)

                    self.answer += (
                        f"Longitud de metadatas: {len(metadatas)}\n\n"
                        f"Chunks url: {total_urls}\n"
                        f"Urls únicas: {num_unique_urls}\n\n"
                        f"Chunks doc: {total_documents}\n"
                        f"Docs únicos: {num_unique_documents}\n\n"
                        "Chunks por documento:\n"
                    )

                    count = 0
                    if document_counts:
                        for index, file_path in enumerate(document_counts, start=count + 1):
                            self.answer += f"{index}. {file_path}, {document_counts[file_path]} chunks\n"
                            count += 1
                    else:
                        self.answer += "(No hay documentos entrenados)\n"

                    self.answer += "\nChunks por url:\n"

                    if url_counts:
                        for index, url in enumerate(url_counts, start=count + 1):
                            self.answer += f"{index}. {url}, {url_counts[url]} chunks\n"
                    else:
                        self.answer += "(No hay URLs entrenadas)\n"
                return self.send_message()

            case "ayuda" | "help":
                self.answer = (
                    "Reconozco los comandos:\n"
                    "/desentrenar para eliminar algún documento de mi entrenamiento.\n"
                    "/entrenar para lanzar el entrenamiento sobre los datos ya cargados.\n"
                    "/estado para conocer los tokens disponibles y las preguntas realizadas.\n"
                    "/lista para mostrar la lista de contenidos sobre la que estoy entrenado.\n"
                    "Y para incorporar un PDF a la carpeta de documentos para entrenar, basta con mandarme el PDF como un documento adjunto."
                )
                return self.send_message()

            case x if re.search(r"^\s*(hola|/start)\b", x):
                self.answer = (
                    "Hola, soy el asistente personalizado para responder desde los contenidos provistos por mi entrenador:\n"
                    f"{self.message.from_user.first_name or ''} {self.message.from_user.last_name or ''}, ¿Que quéres consultar sobre tu base de datos?"
                )
                return self.send_message()

            case x if match := re.search(r"\bbuen[o|a]?s?\s+(d[ií]as?|tardes?|noches?)\b", x):
                time_of_day = match.group(1)
                self.answer = (
                    "Buenas tardes" if "tarde" in time_of_day else "Buenas noches" if "noche" in time_of_day else "Buen día"
                )
                self.answer += ", ¿haceme una consulta sobre tu base de datos?"
                return self.send_message()

            case x if re.search(r"^\bgracias\b[\W_]*$", x) or re.search(r"\bmuchas\s*gracias\b", x):
                self.answer = "De nada!"
                return self.send_message()

            case x if re.search(r"^/desentrenar(?:\s+.*)?$", x):
                message_parts = self.question.split(maxsplit=1)
                if len(message_parts) < 2 or not message_parts[1].isdigit():
                    self.answer = (
                        "Debe ingresar /desentrenar seguido de un número que identifique al documento, 0 para no desentrenar\n"
                        "Ejemplo: /desentrenar 1\n"
                        "Para ver la lista de documentos utilice /lista"
                    )
                    return self.send_message()

                option_selected = int(message_parts[1])
                chroma_collection = self.get_chroma_client()
                chroma_collection_data = chroma_collection.get()
                metadatas = chroma_collection_data.get("metadatas")
                ids = chroma_collection_data.get("ids")

                if metadatas:
                    (
                        total_urls,
                        total_documents,
                        unique_urls,
                        unique_documents,
                        num_unique_urls,
                        num_unique_documents,
                        url_counts,
                        document_counts,
                    ) = self.process_metadata(metadatas)

                    combined_entries = list(document_counts) + list(url_counts)
                    total_entries = len(combined_entries)

                    if option_selected == 0:
                        self.answer = "Desentrenamiento cancelado"
                    elif option_selected > total_entries or option_selected < 0:
                        self.answer = f"El número debe estar entre 1 y {total_entries}"
                    else:
                        # desentrenar y borrarlo de carpeta entrenados
                        selected_value = combined_entries[option_selected - 1]
                        is_document = option_selected <= len(document_counts)

                        # Buscar los IDs a eliminar
                        ids_to_delete = []
                        for i, metadata in enumerate(metadatas):
                            if is_document and metadata.get("file_path") == selected_value and isinstance(ids, list):
                                ids_to_delete.append(ids[i])
                            elif not is_document and metadata.get("url") == selected_value and isinstance(ids, list):
                                ids_to_delete.append(ids[i])

                        if ids_to_delete:
                            chroma_collection.delete(ids=ids_to_delete)
                            os.remove(selected_value)
                            self.answer = f"Borrado exitoso: {selected_value}"
                        else:
                            self.answer = "No se borraron documentos"
                else:
                    self.answer = "No se encontraron documentos para desentrenar."
                return self.send_message()

            case _:
                dbc = self.get_chroma_client(add_embedding=True)

                warning = ""
                results = dbc.similarity_search_with_score(self.question, k=3)
                if results:
                    if results[0][1] > self.client.max_distance:
                        warning = f"La pregunta excede quizá los contenidos específicos de {self.client.business_name}\n"

                    doc = results[0][0]
                    self.source = doc.metadata.get("file_path") or doc.metadata.get("url", "")
                    self.context_text = "\n\n---\n\n".join(
                        [doc.page_content for doc, _ in results]
                    )  # Obtenemos el contexto a partir de los resultados
                else:
                    warning = (
                        "No encuentro resultados dentro del conjunto de datos con los que fuí entrenado,"
                        "la respuesta viene del entrenamiento previo de Open AI:\n\n"
                    )

                sql_prompt = (
                    "Tu tarea es generar una consulta SQL basada únicamente en la información contenida en el contexto proporcionado. "
                    "Devuelve una tupla con dos elementos: "
                    "(1) un valor booleano (0 o 1) que indique si es necesario y posible generar una consulta SQL, y "
                    "(2) SIEMPRE, SIEMPRE, SIEMPRE un string, que contenga la consulta SQL o, en caso de que no se pueda o no sea necesario, una string con la respuesta explicativa clara en lenguaje natural. "
                    f"La base de datos en uso es {self.client.external_db.db_driver.description if self.client.external_db else None}. "
                    "Es obligatorio validar que cada tabla, columna o relación mencionada en la pregunta exista exactamente como aparece en el contexto. "
                    "No intentes interpretar, adivinar ni corregir posibles errores en la pregunta del usuario. "
                    "Si alguna tabla o campo no se encuentra en el contexto, o si la pregunta no requiere SQL para ser respondida, debes devolver de forma no literal (0, <respuesta en leguaje natural>). "
                    "Cuando filtres por texto, asegurate de que las búsquedas sean insensibles a mayúsculas y permitan coincidencias parciales, usando ILIKE, LOWER/UPPER o métodos equivalentes según el motor de base de datos."
                    "RESPETA EL FORMAT OUTPUT tuple(int, string)"
                )

                open_ai_response = self.get_langchain_openai_response(sql_prompt, self.question, self.context_text)

                is_ok = False
                query_or_res = None

                try:
                    parsed = ast.literal_eval(cast(str, open_ai_response.content))
                    if (
                        isinstance(parsed, tuple)
                        and len(parsed) == 2
                        and isinstance(parsed[0], int)
                        and isinstance(parsed[1], str)
                    ):
                        is_ok, query_or_res = bool(parsed[0]), parsed[1]
                except (ValueError, SyntaxError):
                    self.answer = warning + str(open_ai_response.content)

                if not is_ok and query_or_res:
                    self.answer = warning + query_or_res
                elif is_ok and query_or_res:
                    forbidden_ops = {"update", "delete", "insert", "drop", "create", "truncate", "alter", "rename"}
                    if any(op in query_or_res.lower() for op in forbidden_ops):
                        self.answer = warning + "No está permitido generar consultas que alteren la base de datos."
                    else:
                        clean_query = query_or_res.replace("\n", "").strip()
                        self.context_text = f"Resultado de la query ({clean_query}):\n"
                        self.context_text += self.run_external_query(query=query_or_res)
                        prompt = "Responde la pregunta según el contexto CSV provisto a continuación."
                        open_ai_response = self.get_langchain_openai_response(prompt, self.question, self.context_text)
                        self.answer = warning + str(open_ai_response.content)

                return self.send_message()
