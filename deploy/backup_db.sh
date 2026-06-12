#!/bin/bash
# ─────────────────────────────────────────────────────────────
# BIOKO HEALTH — Backup automático de base de datos
# ─────────────────────────────────────────────────────────────
# Instalación (cron diario a las 01:30, antes del sync de las 02:00):
#   sudo crontab -e
#   30 1 * * * /opt/bioko-health/deploy/backup_db.sh >> /opt/bioko-health/logs/backup.log 2>&1
#
# Retención: 30 días locales. Copiar a disco externo/NAS semanalmente.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

BACKUP_DIR="/opt/bioko-health/backups"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Leer credenciales del .env
source <(grep -E '^DATABASE_URL=' /opt/bioko-health/.env)

mkdir -p "$BACKUP_DIR"

if [[ "$DATABASE_URL" == mysql* ]]; then
    # Extraer credenciales de la URL: mysql+pymysql://user:pass@host/dbname
    DB_USER=$(echo "$DATABASE_URL" | sed -E 's|mysql\+pymysql://([^:]+):.*|\1|')
    DB_PASS=$(echo "$DATABASE_URL" | sed -E 's|mysql\+pymysql://[^:]+:([^@]+)@.*|\1|')
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^/]+)/.*|\1|')
    DB_NAME=$(echo "$DATABASE_URL" | sed -E 's|.*/([^?]+).*|\1|')

    FILE="$BACKUP_DIR/bioko_${DB_NAME}_${TIMESTAMP}.sql.gz"
    mysqldump --single-transaction --quick \
        -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" | gzip > "$FILE"
    echo "$(date -Iseconds) | Backup MySQL OK: $FILE ($(du -h "$FILE" | cut -f1))"

elif [[ "$DATABASE_URL" == sqlite* ]]; then
    DB_FILE=$(echo "$DATABASE_URL" | sed 's|sqlite:///||')
    FILE="$BACKUP_DIR/bioko_sqlite_${TIMESTAMP}.db.gz"
    sqlite3 "$DB_FILE" ".backup '$BACKUP_DIR/tmp_backup.db'"
    gzip -c "$BACKUP_DIR/tmp_backup.db" > "$FILE"
    rm -f "$BACKUP_DIR/tmp_backup.db"
    echo "$(date -Iseconds) | Backup SQLite OK: $FILE"
fi

# Eliminar backups antiguos
find "$BACKUP_DIR" -name "bioko_*.gz" -mtime +$RETENTION_DAYS -delete
echo "$(date -Iseconds) | Limpieza: backups de más de $RETENTION_DAYS días eliminados"
