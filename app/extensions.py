"""
BIOKO HEALTH — Extensiones compartidas
Definidas aquí para evitar imports circulares entre app/__init__.py
y los blueprints que necesitan decorar rutas (ej: rate limiting en login).
"""
import os
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
)
