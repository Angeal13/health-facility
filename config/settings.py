import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'bioko-health-dev-key-change-in-production'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BABEL_DEFAULT_LOCALE = 'es'
    WTF_CSRF_ENABLED = True

    FACILITY_CODE = os.environ.get('FACILITY_CODE', 'BIOKO-001')
    FACILITY_NAME = os.environ.get('FACILITY_NAME', 'Hospital General de Malabo')
    FACILITY_TYPE = os.environ.get('FACILITY_TYPE', 'hospital')

    # ── Modo de operación ─────────────────────────────────────────────────
    # local_server   : nodo local, sync periódico (internet o sin red)
    # central_server : servidor central, recibe datos
    # intranet_node  : nodo en intranet de Bioko — sync continuo en tiempo real
    # intranet_central: servidor central en intranet — hub permanente
    FACILITY_MODE = os.environ.get('FACILITY_MODE', 'local_server')

    # ── Red ────────────────────────────────────────────────────────────────
    LAN_HOST = os.environ.get('LAN_HOST', '0.0.0.0')
    LAN_PORT = int(os.environ.get('LAN_PORT', '5000'))
    LAN_URL  = os.environ.get('LAN_URL', '')

    # ── Sync (modo internet — periódico) ──────────────────────────────────
    SYNC_ENABLED        = os.environ.get('SYNC_ENABLED', 'false').lower() == 'true'
    CENTRAL_SERVER_URL  = os.environ.get('CENTRAL_SERVER_URL', '')
    SYNC_API_TOKEN      = os.environ.get('SYNC_API_TOKEN', '')
    SYNC_HOUR           = int(os.environ.get('SYNC_HOUR', '2'))
    SYNC_MINUTE         = int(os.environ.get('SYNC_MINUTE', '0'))

    # ── Intranet — sync continuo ──────────────────────────────────────────
    # INTRANET_MODE=true activa el motor de sync en tiempo real.
    # En lugar de un cron a las 02:00, cada escritura se propaga
    # al servidor central en segundos. Si el enlace cae, se encola
    # localmente y se reenvía cuando se restablece.
    INTRANET_MODE = os.environ.get('INTRANET_MODE', 'false').lower() == 'true'

    # IP o hostname del servidor central en la intranet de Bioko
    # Ejemplo: 10.10.0.1  (IP en la red troncal de la isla)
    INTRANET_CENTRAL_URL = os.environ.get('INTRANET_CENTRAL_URL', '')

    # Con qué frecuencia el nodo verifica nuevos datos del central (segundos)
    # 30 = casi tiempo real; 300 = cada 5 min (para enlaces más lentos)
    INTRANET_PULL_INTERVAL = int(os.environ.get('INTRANET_PULL_INTERVAL', '30'))

    # Reintentos de envío cuando el enlace está inestable
    INTRANET_RETRY_INTERVAL = int(os.environ.get('INTRANET_RETRY_INTERVAL', '10'))

    # Si True, el nodo escribe DIRECTAMENTE en la BD central (requiere
    # conectividad estable y latencia < 50ms — fibra o microondas).
    # Si False, escribe local primero y propaga en background (más robusto).
    INTRANET_WRITE_THROUGH = os.environ.get('INTRANET_WRITE_THROUGH', 'false').lower() == 'true'

    # ── Sesiones ──────────────────────────────────────────────────────────
    SESSION_TYPE            = 'filesystem'
    SESSION_FILE_DIR        = os.path.join(BASE_DIR, '..', 'flask_sessions')
    SESSION_PERMANENT       = False
    SESSION_USE_SIGNER      = True
    PERMANENT_SESSION_LIFETIME = 28800

    # ── Archivos ──────────────────────────────────────────────────────────
    UPLOAD_FOLDER     = os.path.join(BASE_DIR, '..', 'uploads')
    REPORTS_FOLDER    = os.path.join(BASE_DIR, '..', 'reports')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    OUTBREAK_THRESHOLD = int(os.environ.get('OUTBREAK_THRESHOLD', '5'))


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DEV_DATABASE_URL') or
        'sqlite:///' + os.path.join(BASE_DIR, '..', 'bioko_health_dev.db')
    )


class ProductionConfig(Config):
    """Nodo local con internet intermitente — sync diario."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or
        'mysql+pymysql://bioko_user:password@localhost/bioko_health'
    )
    SQLALCHEMY_POOL_SIZE     = int(os.environ.get('DB_POOL_SIZE', '10'))
    SQLALCHEMY_MAX_OVERFLOW  = int(os.environ.get('DB_POOL_OVERFLOW', '20'))
    SQLALCHEMY_POOL_TIMEOUT  = 30
    SQLALCHEMY_POOL_RECYCLE  = 1800
    SQLALCHEMY_POOL_PRE_PING = True


class CentralServerConfig(ProductionConfig):
    """Servidor central — recibe de todos los nodos."""
    FACILITY_MODE   = 'central_server'
    SQLALCHEMY_POOL_SIZE    = int(os.environ.get('DB_POOL_SIZE', '30'))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('DB_POOL_OVERFLOW', '50'))


class IntranetNodeConfig(ProductionConfig):
    """
    Nodo conectado a la intranet de Bioko.
    Sync continuo — escribe local y propaga en segundos.
    Fallback automático si el enlace troncal cae.
    """
    FACILITY_MODE    = 'intranet_node'
    INTRANET_MODE    = True
    SYNC_ENABLED     = True                    # el sync periódico sigue activo como respaldo
    SYNC_HOUR        = 3                       # backup completo a las 03:00 por si acaso
    # Pool más amplio: los nodos de intranet tienen más tráfico concurrente
    SQLALCHEMY_POOL_SIZE    = int(os.environ.get('DB_POOL_SIZE', '15'))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('DB_POOL_OVERFLOW', '25'))


class IntranetCentralConfig(ProductionConfig):
    """
    Servidor central en la intranet de Bioko.
    Recibe escrituras continuas de todos los nodos.
    Pool de conexiones muy grande.
    """
    FACILITY_MODE    = 'intranet_central'
    INTRANET_MODE    = True
    SYNC_ENABLED     = False
    SQLALCHEMY_POOL_SIZE    = int(os.environ.get('DB_POOL_SIZE', '60'))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('DB_POOL_OVERFLOW', '80'))
    SQLALCHEMY_POOL_RECYCLE = 900              # reciclar más frecuente bajo carga alta


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SYNC_ENABLED     = False
    INTRANET_MODE    = False


config = {
    'development':        DevelopmentConfig,
    'production':         ProductionConfig,
    'central':            CentralServerConfig,
    'intranet_node':      IntranetNodeConfig,
    'intranet_central':   IntranetCentralConfig,
    'testing':            TestingConfig,
    'default':            DevelopmentConfig,
}


class InstallationConfig(ProductionConfig):
    """
    Configuración para CUALQUIER instalación sanitaria:
    hospital, clínica o puesto de salud.
    Mismo software — solo cambia FACILITY_TYPE en .env.
    Se conecta ÚNICAMENTE a su nodo provincial (intranet).
    NUNCA habla directamente con otra instalación ni con el central.
    """
    FACILITY_MODE   = 'installation'
    INTRANET_MODE   = True
    SYNC_ENABLED    = True
    # La URL del nodo provincial de esta zona
    PROVINCIAL_NODE_URL  = os.environ.get('PROVINCIAL_NODE_URL', '')
    # Nunca sincronizar directamente con el central nacional
    CENTRAL_SERVER_URL   = ''
    SQLALCHEMY_POOL_SIZE    = int(os.environ.get('DB_POOL_SIZE', '10'))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('DB_POOL_OVERFLOW', '15'))


class ProvincialNodeConfig(ProductionConfig):
    """
    Nodo Provincial — uno por provincia de Guinea Ecuatorial.
    - Recibe datos de todas las instalaciones de su provincia (intranet)
    - Sirve expedientes a instalaciones que los solicitan (intranet)
    - Enruta transferencias inter-provinciales (internet, bajo demanda)
    - Dashboard de brotes y epidemiología provincial (solo lectura para Ministerio)
    - Sincroniza estadísticas epidemiológicas con el central nacional (internet)
    """
    FACILITY_MODE   = 'provincial_node'
    INTRANET_MODE   = True
    SYNC_ENABLED    = True            # Sync epidemiológico con el central
    SQLALCHEMY_POOL_SIZE    = int(os.environ.get('DB_POOL_SIZE', '40'))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get('DB_POOL_OVERFLOW', '60'))
    SQLALCHEMY_POOL_RECYCLE = 900
    # Cuántos días retener expedientes cacheados de otras provincias
    CACHE_EXPEDIENTE_DIAS   = int(os.environ.get('CACHE_EXPEDIENTE_DIAS', '30'))
    # URL del servidor central nacional (solo para sync epidemiológico y transferencias)
    CENTRAL_SERVER_URL      = os.environ.get('CENTRAL_SERVER_URL', '')
    PROVINCIAL_NODE_URL     = ''      # El nodo provincial ES el servidor de la zona


class AnnabonoNodeConfig(ProvincialNodeConfig):
    """
    Nodo de Annobón — conectividad limitada (satélite / barco).
    Sync con el central: semanal o manual.
    Configuración a definir con el Ministerio según infraestructura disponible.
    """
    FACILITY_MODE            = 'annobon_node'
    SYNC_HOUR                = 3
    SYNC_MINUTE              = 0
    # ANNOBON_SYNC_MODE: 'weekly' | 'manual' | 'satellite'
    ANNOBON_SYNC_MODE        = os.environ.get('ANNOBON_SYNC_MODE', 'weekly')
    INTRANET_PULL_INTERVAL   = 300    # Pull cada 5 min (enlace más lento)


# Añadir al dict config
config['installation']     = InstallationConfig
config['provincial_node']  = ProvincialNodeConfig
config['annobon_node']     = AnnabonoNodeConfig
