#!/bin/sh
set -e  # Detener el script si hay un error

echo "🔄 Configurando base de datos MySQL..."

mysql -h"localhost" -P"$MYSQL_DBPORT" -u"root" -p"$MYSQL_ROOT_PASSWORD" -e "GRANT ALL PRIVILEGES ON $MYSQL_DATABASE.* TO '$MYSQL_USER'@'%';"
mysql -h"localhost" -P"$MYSQL_DBPORT" -u"root" -p"$MYSQL_ROOT_PASSWORD" -e "FLUSH PRIVILEGES;"
mysql -h"localhost" -P"$MYSQL_DBPORT" -u"root" -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS $MYSQL_DATABASE;"
mysql -h"localhost" -P"$MYSQL_DBPORT" -u"root" -p"$MYSQL_ROOT_PASSWORD" -e "CREATE DATABASE $MYSQL_DATABASE;"

SQL_FILE="chat_bot_db.sql"
echo "🔄 Importando datos desde $SQL_FILE..."

# Verificar si el archivo SQL existe
if [ -f "/backups/$SQL_FILE" ]; then
    mysql -h"localhost" -P"$MYSQL_DBPORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" < "/backups/$SQL_FILE"
    echo "✅ Datos importados correctamente."
else
    echo "⚠️ Archivo $SQL_FILE no encontrado. Saltando importación."
fi

echo "🚀 Iniciando servidor..."
exec "$@"
