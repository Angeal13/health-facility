"""
BIOKO HEALTH — Application Factory
===================================
Crea y configura la aplicación Flask según el modo del nodo.

Seguridad incorporada:
    - CSRF en todos los formularios (Flask-WTF) — API de sync exenta (usa tokens HMAC)
    - Rate limiting en login (Flask-Limiter)
    - Cabeceras de seguridad HTTP
    - Sesiones con timeout y cookies seguras
"""
import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, request

from app.models.models import db, bcrypt, Usuario
from app.extensions import login_manager, csrf, limiter


def create_app(config_name=None):
    app = Flask(__name__)

    # ── Configuración ──────────────────────────────────────────
    from config import config_by_name
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    app.config.from_object(config_by_name.get(config_name, config_by_name['production']))

    # ── Extensiones ────────────────────────────────────────────
    db.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    # ── Blueprints ─────────────────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.pacientes import pacientes_bp
    from app.routes.consultas import consultas_bp
    from app.routes.enfermedades import enfermedades_bp
    from app.routes.admin import admin_bp
    from app.routes.reportes import reportes_bp
    from app.routes.mapa import mapa_bp
    from app.routes.api_sync import sync_bp
    from app.routes.transferencia import transferencia_bp
    from app.routes.red import red_bp
    from app.routes.nodo_provincial import provincial_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(pacientes_bp, url_prefix='/pacientes')
    app.register_blueprint(consultas_bp, url_prefix='/consultas')
    app.register_blueprint(enfermedades_bp, url_prefix='/enfermedades')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(reportes_bp, url_prefix='/reportes')
    app.register_blueprint(mapa_bp, url_prefix='/mapa')
    app.register_blueprint(sync_bp, url_prefix='/api/sync')
    app.register_blueprint(transferencia_bp, url_prefix='/transferencia')
    app.register_blueprint(red_bp, url_prefix='/red')
    app.register_blueprint(provincial_bp, url_prefix='/provincial')

    # La API de sync entre nodos usa tokens HMAC (X-Bioko-Token), no sesión —
    # por lo tanto se exime de CSRF. NUNCA eximir rutas de navegador.
    csrf.exempt(sync_bp)
    csrf.exempt(provincial_bp)


    # ── Ruta raíz ──────────────────────────────────────────────
    from flask import redirect, url_for
    from flask_login import current_user

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('pacientes.dashboard'))
        return redirect(url_for('auth.login'))

    # ── Contexto global para templates ─────────────────────────
    @app.context_processor
    def inject_globals():
        return {
            'facility_name': app.config.get('FACILITY_NAME'),
            'facility_code': app.config.get('FACILITY_CODE'),
            'facility_mode': app.config.get('FACILITY_MODE'),
        }

    # ── Cabeceras de seguridad ─────────────────────────────────
    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'DENY')
        resp.headers.setdefault('Referrer-Policy', 'same-origin')
        if app.config.get('SESSION_COOKIE_SECURE'):
            resp.headers.setdefault('Strict-Transport-Security',
                                    'max-age=31536000; includeSubDomains')
        return resp

    # ── Páginas de error ───────────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # ── Logging ────────────────────────────────────────────────
    _setup_logging(app)

    # ── Motores de sincronización ──────────────────────────────
    # Solo en el proceso principal (evita doble arranque con el reloader de Flask)
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        from app.utils.sync_scheduler import init_sync
        from app.utils.intranet_sync import init_intranet
        init_sync(app)
        init_intranet(app)

    return app


def _setup_logging(app):
    log_dir = os.path.join(app.root_path, '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(
        os.path.join(log_dir, 'bioko.log'),
        maxBytes=5 * 1024 * 1024, backupCount=10, encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    ))
    handler.setLevel(logging.INFO)

    for name in ('bioko', 'bioko.sync', 'bioko.intranet', 'bioko.provincial'):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

    if not app.debug:
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
