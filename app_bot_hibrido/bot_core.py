from collections import defaultdict
from langchain.prompts import ChatPromptTemplate
from langchain_community.document_loaders import DirectoryLoader, pdf
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from chromadb.api.types import GetResult
import chromadb
import os
import pymupdf
import re
import telebot
import time

from project_chatbot.settings import DEBUG, COLORS
from .models import *


class ChatBot():

    def __init__(self, client_id: int):

        self.client: Client = Client.objects.get(pk=client_id)
        self.user: User = None
        self.output_style: tuple = None
        self.message = None
        self.question = None
        self.answer = None
        self.context_text = ''
        self.source = ''
        self.master_chat_id: int = 2100999603

        self.telegram_api_key = self.client.telegram_api_key_test if DEBUG else self.client.telegram_api_key_prod
        self.chroma_path = self.client.chromadb_test if DEBUG else self.client.chromadb_prod
        self.prompt = self.client.prompt_test if DEBUG else self.client.prompt_prod
        self.open_ai_model = ChatOpenAI(model='gpt-3.5-turbo', temperature=0, openai_api_key=self.client.openai_api_key)
        self.telegram_bot = telebot.TeleBot(self.telegram_api_key)
        self.telegram_bot.message_handler(content_types=['document', 'text'])(self.cmd_start)
    
    def cmd_start(self, message: telebot.types.Message) -> None:

        self.message = message
        self.question = 'ayuda' if self.message.text == '' else message.text.lower() if message.text else ''

        if self.client.bot_closed == 1:
            session, created = Session.objects.get_or_create(
                client=self.client,
                chat_id=self.message.chat.id,
                defaults={
                    "last_name": self.message.from_user.last_name,
                    "first_name": self.message.from_user.first_name,
                    "validation": 1,
                    "context": Context.objects.get(pk=1),
                }
            )
            if created:
                self.answer = 'Por favor, ingrese su dirección de correo electrónico:'
                return self.send_message()
            else:
                if self.question == 'revalidar':
                    session.validation = 1
                    session.save()
                    self.answer = 'Por favor, ingrese su dirección de correo electrónico:'
                    return self.send_message()

                client_users = User.objects.filter(client=self.client)
                match session.validation:
                    case 1: # recibiendo el mail, si existe en la tabla de usuarios pido la contraseña
                        if user := client_users.filter(mail=self.question).first():
                            user.session = session
                            user.save()
                            session.validation = 2
                            session.save()
                            self.answer = f"Muchas gracias, por favor introduzca la contraseña provista por {self.client.business_name}."
                            return self.send_message()
                        else:
                            self.answer = (
                                f"Lo siento, esa dirección de correo electrónico no coincide con ninguna de las informadas por {self.client.business_name}.\n"
                                "Por favor introduzca la dirección de correo electrónico."
                            )
                            return self.send_message()
                    case 2: # solicitando password, si coincide la valido
                        if client_users.filter(session=session, password=self.message.text).exists():
                            session.validation = 3
                            session.save()
                            self.answer = 'La identificación ha quedado registrada, en que puedo ayudar?'
                            return self.send_message()
                        else:
                            self.answer = (
                                f'Lo siento, la contraseña ingresada no coincide con la provista por {self.client.business_name}\n'
                                 'Por favor ingrese nuevamente la contraseña o conteste "revalidar" para cambiar el mail' 
                            )
                            return self.send_message()
                    case 3: # validado al usuario
                        self.user = client_users.filter(session=session).first()
        else:
            self.user = User.objects.filter(client=self.client, session__chat_id=self.message.chat.id).first()

        if message.document : # reviso si vino un documento
            directory_path = os.path.join(self.client.documents_folder, str(self.message.chat.id))
            trained_path = os.path.join(directory_path, 'entrenados')
            os.makedirs(trained_path, exist_ok=True)

            file_name = message.document.file_name
            file_path = os.path.join(trained_path, file_name)
            file_info = self.telegram_bot.get_file(message.document.file_id)
            downloaded_file = self.telegram_bot.download_file(file_info.file_path)
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)

            self.answer = 'Documento descargado.'
            return self.send_message()

        match self.question:
            case '/estado':
                self.answer = f'Para el mes en curso dispones de {self.user.available_tokens} tokens y llevas {self.user.asked_questions} preguntas realizadas.'
                return self.send_message()

            case '/recargar': # uso de este comando??
                self.client = Client.objects.get(pk=self.client.pk)      
                self.answer = 'Datos recargados.'
                return self.send_message()

            case '/stop':
                if self.message.chat.id == self.master_chat_id:
                    self.answer = 'Deteniendo el bot...'
                    self.send_message()
                    self.telegram_bot.stop_polling()
                    return

            case '/entrenar':
                # entrena todos los documentos que encuentre en la carpeta y los mueve a la carpeta de entrenados
                loader = DirectoryLoader(f'{self.client.documents_folder}/{self.message.chat.id}', glob='*.pdf', loader_cls=pdf.PyMuPDFLoader)
                documents = loader.load()

                # Mido si tengo Tokens disponibles para entrenar
                total_palabras = 0
                for d in documents:
                    file = d.metadata['file_path']
                    total_palabras = total_palabras + self.word_counter(file)

                if total_palabras > TokensDisponibles:
                    self.answer = (
                        f'Los documentos que trata de entrenar suman: {total_palabras} tokens'
                        f'Dispone sólo de: {TokensDisponibles} tokens'
                        'Espere al próximo período o considere el upgrade a una suscripción premium.'
                    )
                else:
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size = self.client.chunk_size,
                        chunk_overlap = self.client.chunk_overlap,
                        length_function = len,
                        add_start_index = True,
                    )         
                    chunks = text_splitter.split_documents(documents)

                    if len(chunks) > 0:
                        self.answer = (
                            'Entrenando documentos\n'
                            f'Separamos {len(documents)} documentos en {len(chunks)} chunks.\n'
                        )

                        # Cambiamos la función de embedding para utilizar la de OpenAI
                        embedding_function = OpenAIEmbeddings(api_key=self.client.openai_api_key)

                        db2 = Chroma.from_documents(
                            chunks, 
                            embedding_function, 
                            persist_directory=f'{self.chroma_path}/{self.message.chat.id}'
                        )
                        self.answer += f'Grabados {len(chunks)} a {self.chroma_path}\n'
                        os.system('mv '+ self.client.documents_folder +'/'+str(self.message.chat.id)+'/*.pdf '+ 
                            self.client.documents_folder +'/'+str(self.message.chat.id)+ '/entrenados')

                        # actualizo los TokensDisponibles
                        TokensDisponibles = TokensDisponibles-total_palabras
                        self.user.available_tokens = TokensDisponibles # int en model
                        self.user.save()
                        
                        self.answer += f'Le quedan {TokensDisponibles} tokens'
                    else:
                        self.answer = "No hay documentos para entrenar"
                return self.send_message()

            case '/lista': # lista de materiales entrenados precedidos por un número
                chroma_collection = self.load_collection()
                metadatas = chroma_collection.get('metadatas')
                uris = chroma_collection.get('uris')
                data = chroma_collection.get('data')

                self.answer = (
                    'Lista de documentos entrenados:\n'
                    f'Longitud de ids: {len(chroma_collection.get("ids", []))}\n'
                    f'Longitud de documents: {len(chroma_collection.get("documents", []))}\n'
                )

                if uris:
                    self.answer += f'Longitud de urls: {len(uris)}\n'
                if data:
                    self.answer += f'Longitud de data: {len(data)}\n'
                if metadatas:
                    (
                        total_urls, total_documents, unique_urls, unique_documents,
                        num_unique_urls, num_unique_documents, url_counts, document_counts
                    ) = self.process_metadata(metadatas)

                    self.answer += (
                        f'Longitud de metadatas: {len(metadatas)}\n\n'
                        f'Chunks url: {total_urls}\n'
                        f'Urls únicas: {num_unique_urls}\n\n'
                        f'Chunks doc: {total_documents}\n'
                        f'Docs únicos: {num_unique_documents}\n\n'
                        'Chunks por documento:\n'
                    )

                    for index, file_path in enumerate(document_counts, start=1):
                        self.answer += f'{index}. {file_path}, {document_counts[file_path]}\n'
                        
                    self.answer += '\nChunks por url:\n'

                    for index, url in enumerate(url_counts, start=index+1):
                        self.answer += f'{index}. {url}, {url_counts[url]}\n'
                return self.send_message()

            case 'ayuda' | 'help':
                self.answer = (
                    "Reconozco los comandos:\n"
                    "/db para realizar consultas en la base de datos.\n"
                    "/desentrenar para eliminar algún documento de mi entrenamiento.\n"
                    "/entrenar para lanzar el entrenamiento sobre los datos ya cargados.\n"
                    "/estado para conocer los tokens disponibles y las preguntas realizadas.\n"
                    "/lista para mostrar la lista de contenidos sobre la que estoy entrenado.\n"
                    "Y para incorporar un PDF a la carpeta de documentos para entrenar, basta con mandarme el PDF como un documento adjunto."
                )
                return self.send_message()

            case x if re.search(r"^\s*(hola|/start)\b", x):
                self.answer = (
                    'Hola, soy el asistente personalizado para responder desde los contenidos provistos por mi entrenador:\n'
                    f'{self.message.from_user.first_name or ''} {self.message.from_user.last_name or ''}, ¿en qué puedo ayudar?'
                )
                return self.send_message()

            case x if match := re.search(r"\bbuen[o|a]?s?\s+(d[ií]as?|tardes?|noches?)\b", x):
                time_of_day = match.group(1)
                self.answer = 'Buenas tardes' if 'tarde' in time_of_day else 'Buenas noches' if 'noche' in time_of_day  else 'Buen día'
                self.answer += ', ¿en qué puedo ayudar?'
                return self.send_message()

            case x if re.search(r"^\bgracias\b[\W_]*$", x) or re.search(r"\bmuchas\s*gracias\b", x):
                self.answer = 'De nada!'
                return self.send_message()

            case x if re.search(r'^/desentrenar(?:\s+.*)?$', x):
                message_parts = self.question.split(maxsplit=1)
                if len(message_parts) < 2 or not message_parts[1].isdigit():
                    self.answer = (
                        'Debe ingresar /desentrenar seguido de un número que identifique al documento, 0 para no desentrenar\n'
                        'Ejemplo: /desentrenar 1\n'
                        'Para ver la lista de documentos utilice /lista'
                    )
                    return self.send_message()

                option_selected = int(message_parts[1])
                chroma_collection = self.load_collection()
                metadatas = chroma_collection.get('metadatas')
                ids = chroma_collection.get('ids')

                if metadatas:
                    (
                        total_urls, total_documents, unique_urls, unique_documents,
                        num_unique_urls, num_unique_documents, url_counts, document_counts
                    ) = self.process_metadata(metadatas)

                    if option_selected == 0:
                        self.answer = 'Desentrenamiento cancelado'
                    elif option_selected > num_unique_documents + num_unique_urls:
                        self.answer = f'El número debe estar entre 1 y {num_unique_documents + num_unique_urls}'
                    elif 0 < option_selected <= num_unique_documents + num_unique_urls:
                        # desentrenar y lo borrar de carpeta entrenados
                        document, url, found = None, None, False

                        for index, file_path in enumerate(document_counts, start=1):
                            if found:
                                break
                            elif index == option_selected:
                                document = file_path
                                found = True
                        
                        for index, url_path in enumerate(url_counts, start=index+1):
                            if found:
                                break
                            elif index == option_selected:
                                url = url_path
                                found = True

                        # recuperar el documento que corresponde a ese nombre
                        ids_to_delete = []
                        for index, metadata in enumerate(metadatas):
                            if 'url' in metadata:
                                if url == metadata['url']:
                                    ids_to_delete.append(ids[index])

                            if 'file_path' in metadata:
                                if document == metadata['file_path']:
                                    ids_to_delete.append(ids[index])

                        client = chromadb.PersistentClient(path=f'{self.chroma_path}/{self.message.chat.id}')
                        collection = client.get_collection('langchain')

                        if len(ids_to_delete) > 0:
                            collection.delete(ids=ids_to_delete)
                            self.answer = f'Borrado exitoso: {document or url}'
                        else:
                            self.answer = 'No se borraron documentos'
                else:
                    self.answer = 'No se encontraron documentos para desentrenar.'
                return self.send_message()

            case x if re.search(r'^/db(?:\s+.*)?$', x):
                message_parts = self.question.split(maxsplit=1)
                self.print_out(message_parts, 'red')
                if len(message_parts) < 2:
                    self.answer = 'Debe ingresar /db seguido de una consulta. Ejemplo:\n/db Catidad de productos en stock.'
                    return self.send_message()

                sql_prompt = 'Devuelva el código SQL necesario para obtener los datos necesarios para responder la siguiente pregunta.\n'
                context_text = '' # diccionario de datos???
                open_ai_response = self.open_ai_model_invoke(sql_prompt, message_parts[1], context_text)
                self.answer = open_ai_response.content # sql query en este punto

                # abrir la base de datos comercial
                # ejecutar query dentro de un try except
                # si no hay error al ejecutar 
                #   convertir los datos en una tabla en texto.
                #   crear un PROMPT apropiado para navegar los datos
                #   mandar a la IA la pregunta original cargando los datos en la ventana de contexto
                #   mandar al usuario la respuesta de la IA
                # si hay error al ejecutar

                return self.send_message()

            case _:
                # Inicializamos la base de datos Chroma con la nueva función de embedding
                dbc = Chroma(
                    persist_directory=f'{self.chroma_path}/{self.message.chat.id}', 
                    embedding_function=OpenAIEmbeddings(api_key=self.client.openai_api_key)
                )

                warning = ''
                results = dbc.similarity_search_with_score(self.question, k=3)
                if results:
                    if results[0][1] > self.client.max_distance:
                        warning = f'La pregunta excede quizá los contenidos específicos de {self.client.business_name}\n'

                    doc = results[0][0]
                    self.source = doc.metadata.get('file_path') or doc.metadata.get('url', url)
                    self.context_text = '\n\n---\n\n'.join([doc.page_content for doc, _ in results]) # Obtenemos el contexto a partir de los resultados
                else:
                    warning = (
                        'No encuentro resultados dentro del conjunto de datos con los que fuí entrenado,'
                        'la respuesta viene del entrenamiento previo de Open AI:\n\n'
                    )
                
                # Creamos el template para obtener la pregunta
                open_ai_response = self.open_ai_model_invoke(self.prompt, self.question, self.context_text)
                self.answer = warning + open_ai_response.content

                return self.send_message()

    def load_collection(self) -> GetResult:

        client = chromadb.PersistentClient(path=f'{self.chroma_path}/{self.message.chat.id}')
        collection = client.get_collection('langchain')

        return collection.get()
    
    def open_ai_model_invoke(self, prompt: str, question: str, context: str = None):

        self.user.asked_questions += 1
        self.user.save() # Actualizo las preguntas realizadas

        if self.user.asked_questions > 1000: # Espera una décima segundo más por cada pregunta adicional
            delta = (self.user.asked_questions-1000)/10
            time.sleep(delta)

        template = ChatPromptTemplate.from_template(prompt + 'Pregunta: {question}\n' + 'Contexto: {context}')
        prompt = template.format(question=question, context=context or 'No se especificó contexto')
        
        return self.open_ai_model.invoke(prompt)

    def print_out(self, message: str, color_style: COLORS=None) -> None:
        
        output, style = self.output_style
        color_styles = {
            'green': style.SUCCESS,
            'green-light': style.SQL_COLTYPE,
            'yellow': style.WARNING,
            'yellow-light': style.SQL_KEYWORD,
            'red': style.ERROR,
            'red-light': style.NOTICE,
            'blue': style.MIGRATE_HEADING,
            'blue-light': style.HTTP_NOT_MODIFIED,
            'magenta': style.HTTP_SERVER_ERROR,
            'white': style.SQL_TABLE
        }.get(color_style, style.SUCCESS)
         
        output.write(color_styles(message))

    def process_metadata(self, metadata_list: list):

        total_urls, total_documents = 0, 0
        unique_urls, unique_documents = set(), set()
        url_counts, document_counts = defaultdict(int), defaultdict(int)

        for metadata in metadata_list:
            if 'url' in metadata:
                total_urls += 1
                url_counts[metadata['url']] += 1
                unique_urls.add(metadata['url'])

            if 'file_path' in metadata:
                total_documents += 1
                document_counts[metadata['file_path']] += 1
                unique_documents.add(metadata['file_path'])

        return (
            total_urls, total_documents, 
            list(unique_urls), list(unique_documents), 
            len(unique_urls), len(unique_documents), 
            dict(url_counts), dict(document_counts)
        )

    def send_message(self) -> None:
        
        Log.objects.create(
            question=self.question,
            answer=self.answer,
            last_name=self.message.from_user.last_name,
            first_name=self.message.from_user.first_name,
            context=self.context_text,
            client=self.client,
            test=1 if DEBUG else 0,
            source=self.source
        )

        self.telegram_bot.send_message(self.message.chat.id, self.answer)
        self.answer = None

    def word_counter(self, file) -> int:

        with pymupdf.open(file) as doc:
            text = []
            for page in doc:
                text.append(page.get_text('text'))
            
            full_text = ''.join(text)
            full_text = full_text.replace('�', '')
            words = full_text.split()

            return len(words)
