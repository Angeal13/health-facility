#!/bin/bash
# Add backup to root crontab — run once after installation
(crontab -l 2>/dev/null; echo "0 1 * * * /opt/bioko_health/scripts/backup.sh") | crontab -
echo "Backup cron configured: daily at 01:00"
