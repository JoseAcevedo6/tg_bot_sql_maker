#!/bin/bash

# Iniciar MySQL
docker compose -f docker-compose-mysql.yml up -d

# Esperar a que MySQL esté listo
echo "⏳ Esperando a que MySQL esté listo..."
until docker exec mysql mysqladmin ping -h"localhost" --silent; do
    sleep 2
done
echo "✅ MySQL está listo."

# Iniciar el ChatBot solo cuando MySQL esté listo
docker compose up -d

echo "🚀 Base de datos y ChatBot listos."