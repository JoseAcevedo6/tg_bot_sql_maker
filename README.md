# 📌 Guía para configurar y ejecutar el proyecto

## 🗂️ Agregar base de datos
Colocar el archivo `chat_bot_db.sql` en la carpeta `/backups` del proyecto.

## 🏗️ Crear los contenedores
Ejecutar el siguiente script para levantar los contenedores de MySQL y la aplicación:

```sh
./scripts/init_containers.sh
```

## 🤖 Iniciar un bot de Telegram  
Para iniciar el bot de Telegram con un cliente configurado en la base de datos, usar:

```sh
./scripts/init_bot.sh
```

Si se quiere probar con el cliente de testing, usar el ID `20`:

## 🏠 Acceder al contenedor de la aplicación  
Para ingresar al contenedor del proyecto, ejecutar:  

```sh
docker exec -it chat_bot_app sh
```

## ⚙️ Comandos útiles dentro del contenedor del proyecto  
Una vez dentro del contenedor, se pueden ejecutar los siguientes comandos:

- **Ejecutar el servidor de Django**  
  ```sh
  python manage.py runserver
  ```

- **Abrir el shell de Django**  
  ```sh
  python manage.py shell
  ```

- **Ejecutar el bot de Telegram con un cliente específico**  
  ```sh
  python manage.py telegram_bot --client_id=some_client_id
  ```

## 🛠️ Acceder a la base de datos desde el contenedor
1. Ingresar al contenedor de MySQL:  
   ```sh
   docker exec -it mysql sh
   ```
2. Luego, acceder a MySQL dentro del contenedor:  
   ```sh
   mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"
   ```

## 📌 También puedes ingresar a la base de datos desde la interfaz web de Django Admin  
Siempre que el proyecto esté iniciado con `runserver`, puedes acceder a la interfaz de administración:

**🔗 URL de acceso:**  
```
http://localhost:8000/admin/
```

**Si aún no tienes un superusuario, créalo desde el interior del contenedor con:**  

```sh
python manage.py createsuperuser
```

**Inicia sesión con las credenciales configuradas y gestiona la base de datos desde la interfaz.** 🚀

## Recuerda que los comandos y scripts deben ser ejecutados desde la raíz del proyecto. 💭
