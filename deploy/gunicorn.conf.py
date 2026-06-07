import multiprocessing, os

# Installation (hospital/clinic/puesto) — bind only to LAN interface
# Tablets connect via local WiFi; this server is not reachable from internet
bind = f"LAN_IP_PLACEHOLDER:{os.environ.get('LAN_PORT', '5000')}"
backlog = 256
workers = int(os.environ.get('GUNICORN_WORKERS', min(multiprocessing.cpu_count() * 2 + 1, 7)))
worker_class = "sync"
threads = 2
timeout = 120
keepalive = 5
graceful_timeout = 30
accesslog = "/var/log/bioko_health/gunicorn_access.log"
errorlog  = "/var/log/bioko_health/gunicorn_error.log"
loglevel  = "warning"
pidfile   = "/run/bioko_health/gunicorn.pid"
user = "bioko"
group = "bioko"
daemon = False
