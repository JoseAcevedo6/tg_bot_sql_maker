#!/bin/bash

# Solicitar el client_id al usuario
echo "Por favor, ingresa el número de cliente:"
read -r CLIENT_ID

# Ejecutar el comando dentro del contenedor chat_bot_app
echo "🔄 Iniciando bot 🤖 cliente id $CLIENT_ID"
docker exec -it chat_bot_app sh -c "python manage.py telegram_bot --client_id=$CLIENT_ID"
