#!/bin/bash
# BIOKO HEALTH — Backup automático de base de datos
# Cron: 0 1 * * * /opt/bioko_health/scripts/backup.sh
set -euo pipefail

APP_DIR="/opt/bioko_health"
BACKUP_DIR="$APP_DIR/backups"
LOG="$APP_DIR/logs/backup.log"
MAX_BACKUPS=30  # Mantener últimos 30 días

mkdir -p "$BACKUP_DIR"

# Leer credenciales de .env
source "$APP_DIR/.env" 2>/dev/null || true

# Extraer user/pass/db de DATABASE_URL
DB_URL="${DATABASE_URL:-}"
if [[ -z "$DB_URL" ]]; then
    echo "[$(date)] ERROR: DATABASE_URL no configurado" >> "$LOG"
    exit 1
fi

# Solo backup para MySQL
if [[ "$DB_URL" == mysql* ]]; then
    DB_USER=$(echo "$DB_URL" | grep -oP '(?<=://)[^:]+')
    DB_PASS=$(echo "$DB_URL" | grep -oP '(?<=:)[^@]+(?=@)')
    DB_HOST=$(echo "$DB_URL" | grep -oP '(?<=@)[^/]+(?=/)')
    DB_NAME=$(echo "$DB_URL" | grep -oP '[^/]+$')

    BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql.gz"

    mysqldump -u"$DB_USER" -p"$DB_PASS" -h"$DB_HOST" \
        --single-transaction --routines --triggers \
        "$DB_NAME" | gzip > "$BACKUP_FILE"

    SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
    echo "[$(date)] OK: $BACKUP_FILE ($SIZE)" >> "$LOG"

    # Eliminar backups más antiguos que MAX_BACKUPS días
    find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +$MAX_BACKUPS -delete

    # Contar backups restantes
    COUNT=$(ls "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null | wc -l)
    echo "[$(date)] Backups conservados: $COUNT" >> "$LOG"
else
    # SQLite backup
    DB_PATH=$(echo "$DB_URL" | sed 's|sqlite:///||')
    BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).db.gz"
    gzip -c "$DB_PATH" > "$BACKUP_FILE"
    echo "[$(date)] SQLite backup: $BACKUP_FILE" >> "$LOG"
fi
