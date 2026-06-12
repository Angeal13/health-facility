"""
BIOKO HEALTH — Configuración Central
=====================================
Lee variables del archivo .env y define los perfiles de configuración.

Modos de nodo (FACILITY_MODE):
    facility        : Instalación sanitaria (hospital/clínica/puesto)
    provincial_node : Nodo provincial (1 por provincia)
    central_server  : Servidor central del Ministerio (único)
    annobon_node    : Nodo especial de Annobón (conectividad intermitente)
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


def _bool(key, default='false'):
    return os.environ.get(key, default).strip().lower() in ('true', '1', 'yes', 'on')


class Config:
    """Configuración base — compartida por todos los modos."""

    # ── Seguridad ──────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY no configurada. Genere una con:\n"
            "  python3 -c \"import secrets; print(secrets.token_hex(32))\"\n"
            "y añádala al archivo .env"
        )

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = _bool('SESSION_COOKIE_SECURE', 'false')  # true detrás de HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_HTTPONLY = True

    # CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 8 * 3600  # igual que la sesión

    # ── Base de datos ──────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(basedir, 'instance', 'bioko_health.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
    }
    # Pool extra para MySQL (ignorado por SQLite)
    if 'mysql' in SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_ENGINE_OPTIONS.update({
            'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
            'max_overflow': int(os.environ.get('DB_POOL_OVERFLOW', 20)),
        })

    # ── Identidad del nodo ─────────────────────────────────────
    FACILITY_CODE = os.environ.get('FACILITY_CODE', 'LOCAL')
    FACILITY_NAME = os.environ.get('FACILITY_NAME', 'Instalación Local')
    FACILITY_TYPE = os.environ.get('FACILITY_TYPE', 'clinica')
    FACILITY_MODE = os.environ.get('FACILITY_MODE', 'facility')
    PROVINCIA_CODIGO = os.environ.get('PROVINCIA_CODIGO', '')

    # ── Red ────────────────────────────────────────────────────
    LAN_HOST = os.environ.get('LAN_HOST', '0.0.0.0')
    LAN_PORT = int(os.environ.get('LAN_PORT', 5000))
    LAN_URL = os.environ.get('LAN_URL', '')

    # ── Sincronización ─────────────────────────────────────────
    SYNC_ENABLED = _bool('SYNC_ENABLED')
    CENTRAL_SERVER_URL = os.environ.get('CENTRAL_SERVER_URL', '')
    SYNC_API_TOKEN = os.environ.get('SYNC_API_TOKEN', '')
    SYNC_HOUR = int(os.environ.get('SYNC_HOUR', 2))
    SYNC_MINUTE = int(os.environ.get('SYNC_MINUTE', 0))

    # Intranet (tiempo real, fibra óptica provincial)
    INTRANET_MODE = _bool('INTRANET_MODE')
    INTRANET_CENTRAL_URL = os.environ.get('INTRANET_CENTRAL_URL', '')
    INTRANET_PULL_INTERVAL = int(os.environ.get('INTRANET_PULL_INTERVAL', 30))
    INTRANET_RETRY_INTERVAL = int(os.environ.get('INTRANET_RETRY_INTERVAL', 10))

    # Annobón (conectividad intermitente)
    ANNOBON_SYNC_MODE = os.environ.get('ANNOBON_SYNC_MODE', 'weekly')

    # ── Expedientes inter-provinciales ─────────────────────────
    CACHE_EXPEDIENTE_DIAS = int(os.environ.get('CACHE_EXPEDIENTE_DIAS', 30))

    # ── Epidemiología ──────────────────────────────────────────
    OUTBREAK_THRESHOLD = int(os.environ.get('OUTBREAK_THRESHOLD', 5))

    # ── Rate limiting ──────────────────────────────────────────
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    LOGIN_RATE_LIMIT = os.environ.get('LOGIN_RATE_LIMIT', '10 per minute')


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = _bool('SESSION_COOKIE_SECURE', 'true')


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    # Los modos de nodo usan producción por defecto
    'facility': ProductionConfig,
    'provincial_node': ProductionConfig,
    'central_server': ProductionConfig,
    'annobon_node': ProductionConfig,
}
