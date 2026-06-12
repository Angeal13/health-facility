"""
BIOKO HEALTH — Configuración de Gunicorn (producción)
Uso: gunicorn -c deploy/gunicorn.conf.py wsgi:app
"""
import multiprocessing

bind = "127.0.0.1:5000"          # Solo localhost — nginx hace de proxy
workers = 1                       # IMPORTANTE: 1 worker.
# Los motores de sync (APScheduler + cola en memoria) viven en el proceso.
# Múltiples workers duplicarían los jobs de sincronización.
# Para más concurrencia usar threads:
threads = 8
worker_class = "gthread"
timeout = 60
keepalive = 5

# Logging
accesslog = "logs/gunicorn-access.log"
errorlog = "logs/gunicorn-error.log"
loglevel = "info"

# Seguridad
limit_request_line = 4096
limit_request_fields = 100
