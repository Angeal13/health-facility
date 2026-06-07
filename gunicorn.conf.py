import multiprocessing, os

# Edge Server Configuration — optimized for multiple tablets/laptops
# Tablets connect via local WiFi; this server is not reachable from internet
bind = f"LAN_IP_PLACEHOLDER:{os.environ.get('LAN_PORT', '5000')}"
backlog = 512

# Use more workers for the Edge Server role (i7 CPU typically has 8-12+ cores)
# Formula: (2 x cores) + 1. We'll cap it at 12 to avoid excessive RAM usage.
workers = int(os.environ.get('GUNICORN_WORKERS', min(multiprocessing.cpu_count() * 2 + 1, 12)))
worker_class = "sync"
threads = 4  # Increased threads per worker for better concurrent handling
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
