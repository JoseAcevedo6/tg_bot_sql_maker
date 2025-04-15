#!/bin/sh
set -e

export $(grep -v '^#' .env | xargs)

SQL_FILE="fakedb_to_test.sql"
LOCAL_PATH="./backups/$SQL_FILE"

if [ -f "$LOCAL_PATH" ]; then
    docker exec -i mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" < "$LOCAL_PATH"
    echo "✅ Datos importados correctamente."
else
    echo "⚠️ Archivo $SQL_FILE no encontrado en ./backups"
fi
