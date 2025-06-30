from django.db import models


class Client(models.Model):

    id = models.AutoField(db_column="idcliente", primary_key=True)
    business_name = models.CharField(db_column="razonsocial", max_length=200)
    subscribed_date = models.DateField(db_column="fechaalta")
    unsubscribed_date = models.DateField(db_column="fechabaja", null=True, blank=True)
    telegram_api_key_test = models.CharField(db_column="apikeytelegramprueba", max_length=200)
    telegram_api_key_prod = models.CharField(db_column="apikeytelegramproduccion", max_length=200)
    openai_api_key = models.CharField(db_column="apikeyopenai", max_length=200)
    chromadb_test = models.CharField(db_column="chromadbprueba", max_length=200)
    chromadb_prod = models.CharField(db_column="chromadbproduccion", max_length=200)
    bot_username_test = models.CharField(db_column="usernamebotprueba", max_length=200)
    bot_username_prod = models.CharField(db_column="usernamebotproduccion", max_length=200)
    documents_folder = models.CharField(db_column="carpetadocumentos", max_length=200)
    extra_documents_folder = models.CharField(db_column="carpeta_documentos", max_length=200, null=True, blank=True)
    chunk_size = models.IntegerField(db_column="chunksize")
    chunk_overlap = models.IntegerField(db_column="chunkoverlap")
    max_distance = models.FloatField(db_column="distanciamaxima")
    prompt_test = models.CharField(db_column="promptprueba", max_length=1600)
    prompt_prod = models.CharField(db_column="promptproduccion", max_length=1600)
    bot_closed = models.IntegerField(db_column="bot_cerrado")

    class Meta:
        db_table = "clientes"
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return self.business_name


class DatabaseDriver(models.Model):

    description = models.CharField(max_length=100)
    driver = models.CharField(max_length=100)

    def __str__(self):
        return self.description

    class Meta:
        verbose_name = "Database Driver"
        verbose_name_plural = "Database Drivers"


class ExternalDatabase(models.Model):

    client = models.OneToOneField(Client, related_name="external_db", on_delete=models.CASCADE)
    db_driver = models.ForeignKey(DatabaseDriver, on_delete=models.CASCADE)
    host = models.CharField(max_length=255)
    port = models.IntegerField()
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    database = models.CharField(max_length=255)
    driver = models.CharField(max_length=100, null=True, blank=True)
        # Optional database driver name, used mainly for SQL Server or other databases requiring specific driver configuration.

    class Meta:
        verbose_name = "External Database"
        verbose_name_plural = "External Databases"

    def get_sqlalchemy_params(self) -> dict:
        data = {
            "drivername": self.db_driver.driver,
            "username": self.username,
            "password": self.password,
            "host": self.host,
            "port": self.port,
            "database": self.database,
        }

        if self.driver:
            data["query"] = {"driver": self.driver}

        return data


class Context(models.Model):

    id = models.AutoField(db_column="idContexto", primary_key=True)
    context = models.CharField(db_column="Contexto", max_length=45)
    client = models.ForeignKey(Client, db_column="IdCliente", related_name="contexts", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "contextos"
        verbose_name = "Context"
        verbose_name_plural = "Contexts"


class Course(models.Model):

    id = models.AutoField(db_column="IdCurso", primary_key=True)
    name = models.CharField(db_column="DsCurso", max_length=100, unique=True)
    is_active = models.IntegerField(db_column="Vigente", default=1)
    client = models.ForeignKey(Client, db_column="IdCliente", related_name="courses", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "cursos"
        verbose_name = "Course"
        verbose_name_plural = "Courses"


class Log(models.Model):

    id = models.AutoField(db_column="Id", primary_key=True)
    question = models.TextField(db_column="Pregunta", null=True, blank=True)
    answer = models.TextField(db_column="Respuesta", null=True, blank=True)
    last_name = models.CharField(db_column="Apellido", max_length=100, null=True, blank=True)
    first_name = models.CharField(db_column="Nombre", max_length=100, null=True, blank=True)
    context = models.TextField(db_column="Contexto", null=True, blank=True)
    test = models.IntegerField(db_column="Prueba")
    source = models.CharField(db_column="Source", max_length=200, null=True, blank=True)
    client = models.ForeignKey(Client, db_column="IdCliente", related_name="logs", on_delete=models.CASCADE)
    date = models.DateField(db_column="Fecha", auto_now_add=True)
    time = models.TimeField(db_column="Hora", auto_now_add=True)

    class Meta:
        db_table = "log"
        verbose_name = "Log"
        verbose_name_plural = "Logs"


class Session(models.Model):

    chat_id = models.BigIntegerField(db_column="ChatId")
    last_name = models.CharField(db_column="Apellido", max_length=100, null=True, blank=True)
    first_name = models.CharField(db_column="Nombre", max_length=100, null=True, blank=True)
    validation = models.IntegerField(db_column="Validacion", default=0)
    client = models.ForeignKey(Client, db_column="IdCliente", related_name="sessions", on_delete=models.CASCADE)
    context = models.ForeignKey(Context, db_column="IdContexto", related_name="sessions", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "sesiones"
        verbose_name = "Session"
        verbose_name_plural = "Sessions"
        unique_together = ("chat_id", "client")


class Question(models.Model):

    id = models.AutoField(db_column="idPregunta", primary_key=True)
    chat_id = models.BigIntegerField(db_column="ChatId", null=True, blank=True)
    question = models.TextField(db_column="Pregunta")
    client = models.ForeignKey(Client, db_column="IdCliente", related_name="questions", on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(db_column="Fecha", auto_now_add=True)
    time = models.TimeField(db_column="Hora", auto_now_add=True)

    class Meta:
        db_table = "preguntas"
        verbose_name = "Question"
        verbose_name_plural = "Questions"


class Answer(models.Model):

    id = models.AutoField(db_column="IdRespuesta", primary_key=True)
    chat_id = models.BigIntegerField(db_column="ChatId", null=True, blank=True)
    answer = models.TextField(db_column="Respuesta", null=True, blank=True)
    question = models.ForeignKey(Question, db_column="IdPregunta", related_name="answers", on_delete=models.SET_NULL, null=True, blank=True)
    client = models.ForeignKey(Client, db_column="IdCliente", related_name="answers", on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(db_column="Fecha", auto_now_add=True)
    time = models.TimeField(db_column="Hora", auto_now_add=True)

    class Meta:
        db_table = "respuestas"
        verbose_name = "Answer"
        verbose_name_plural = "Answers"


class Text(models.Model):

    text_id = models.IntegerField(db_column="IdTexto")
    text = models.CharField(db_column="Texto", max_length=2048)
    file = models.CharField(db_column="Archivo", max_length=512, null=True, blank=True)
    html = models.IntegerField(db_column="HTML", null=True, blank=True)
    client = models.ForeignKey(Client, db_column="IdCliente", related_name="texts", on_delete=models.CASCADE)
    context = models.ForeignKey(Context, db_column="IdContexto", related_name="texts", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "textos"
        verbose_name = "Text"
        verbose_name_plural = "Texts"
        unique_together = ("text_id", "client")


class Synonym(models.Model):

    id = models.AutoField(db_column="IdSinonimo", primary_key=True)
    synonym = models.CharField(db_column="Sinonimo", max_length=45)
    client = models.ForeignKey(Client, db_column="IdCliente", related_name="synonyms", on_delete=models.SET_NULL, null=True, blank=True)
    context = models.ForeignKey(Context, db_column="IdContexto", related_name="synonyms", on_delete=models.SET_NULL, null=True, blank=True)
    text = models.ForeignKey(Text, db_column="IdTexto", related_name="synonyms", on_delete=models.CASCADE)

    class Meta:
        db_table = "sinonimos"
        verbose_name = "Synonym"
        verbose_name_plural = "Synonyms"


class TextCourseContext(models.Model):

    client = models.ForeignKey(Client, db_column="IdCliente", related_name="text_course_contexts", on_delete=models.CASCADE)
    context = models.ForeignKey(Context, db_column="IdContexto", related_name="text_course_contexts", on_delete=models.CASCADE)
    course = models.ForeignKey(Course, db_column="IdCurso", related_name="text_course_contexts", on_delete=models.CASCADE)
    text = models.ForeignKey(Text, db_column="IdTexto", related_name="text_course_contexts", on_delete=models.CASCADE)

    class Meta:
        db_table = "textoscursoycontexto"
        verbose_name = "TextCourseContext"
        verbose_name_plural = "TextCourseContext's"
        unique_together = ("client", "context", "course")


class Token(models.Model):

    id = models.AutoField(db_column="IdToken", primary_key=True)
    description = models.CharField(db_column="Descripcion", max_length=45)
    token = models.CharField(db_column="Token", max_length=50)
    test = models.SmallIntegerField(db_column="Prueba", null=True, blank=True)

    class Meta:
        db_table = "tokens"
        verbose_name = "Token"
        verbose_name_plural = "Tokens"


class User(models.Model):

    id = models.AutoField(db_column="IdUsuario", primary_key=True)
    mail = models.CharField(db_column="mail", max_length=200)
    password = models.CharField(db_column="clave", max_length=50)
    available_tokens = models.BigIntegerField(db_column="TokensDisponibles", null=True, blank=True)
    asked_questions = models.IntegerField(db_column="PreguntasRealizadas", null=True, blank=True)
    category = models.CharField(db_column="Categoria", max_length=45, null=True, blank=True)
    is_teacher = models.SmallIntegerField(db_column="EsProfesor", default=0)
    session = models.ForeignKey(Session, db_column="ChatId", related_name="users", on_delete=models.SET_NULL, null=True, blank=True)
    client = models.ForeignKey(Client, db_column="IdCliente", related_name="users", on_delete=models.CASCADE)

    class Meta:
        db_table = "usuarios"
        verbose_name = "User"
        verbose_name_plural = "Users"
