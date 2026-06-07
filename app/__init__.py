import os
import logging
from flask import Flask, render_template
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_babel import Babel
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.models.models import db, bcrypt, Usuario
from config.settings import config

migrate = Migrate()
login_manager = LoginManager()
babel = Babel()
sess = Session()
limiter = Limiter(key_func=get_remote_address, default_limits=[])

log = logging.getLogger('bioko')


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    app.config.from_object(config[config_name])

    # ── Logging ───────────────────────────────────────────────
    if not app.debug:
        log_dir = os.path.join(app.root_path, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.FileHandler(os.path.join(log_dir, 'bioko.log'))
        fh.setLevel(logging.WARNING)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s'
        ))
        app.logger.addHandler(fh)

    # ── Create folders ────────────────────────────────────────
    for folder in ['UPLOAD_FOLDER', 'REPORTS_FOLDER', 'SESSION_FILE_DIR']:
        path = app.config.get(folder)
        if path:
            os.makedirs(path, exist_ok=True)

    # ── Extensions ────────────────────────────────────────────
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    babel.init_app(app)
    sess.init_app(app)
    limiter.init_app(app)

    # ── Login manager ─────────────────────────────────────────
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    # ── Blueprints ────────────────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.pacientes import pacientes_bp
    from app.routes.consultas import consultas_bp
    from app.routes.enfermedades import enfermedades_bp
    from app.routes.mapa import mapa_bp
    from app.routes.reportes import reportes_bp
    from app.routes.admin import admin_bp
    from app.routes.api_sync import sync_bp
    from app.routes.transferencia import transferencia_bp
    from app.routes.red import red_bp
    from app.routes.nodo_provincial import provincial_bp

    app.register_blueprint(auth_bp,         url_prefix='/auth')
    app.register_blueprint(pacientes_bp,    url_prefix='/pacientes')
    app.register_blueprint(consultas_bp,    url_prefix='/consultas')
    app.register_blueprint(enfermedades_bp, url_prefix='/enfermedades')
    app.register_blueprint(mapa_bp,         url_prefix='/mapa')
    app.register_blueprint(reportes_bp,     url_prefix='/reportes')
    app.register_blueprint(admin_bp,        url_prefix='/admin')
    app.register_blueprint(sync_bp,         url_prefix='/api/sync')
    app.register_blueprint(transferencia_bp,url_prefix='/transferencia')
    app.register_blueprint(red_bp,          url_prefix='/red')
    app.register_blueprint(provincial_bp,   url_prefix='/provincial')

    # ── Rate limiting on login ─────────────────────────────────
    limiter.limit("10 per minute")(auth_bp)

    # ── Schedulers ────────────────────────────────────────────
    from app.utils.sync_scheduler import init_sync
    init_sync(app)

    from app.utils.intranet_sync import init_intranet
    init_intranet(app)

    # ── Error handlers ────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        log.exception("Internal server error")
        return render_template('errors/500.html'), 500

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('errors/429.html'), 429

    # ── Root redirect ─────────────────────────────────────────
    from flask import redirect, url_for
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # ── Context processors ────────────────────────────────────
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from datetime import datetime
        return dict(
            current_user=current_user,
            facility_name=app.config.get('FACILITY_NAME', 'Bioko Health'),
            facility_code=app.config.get('FACILITY_CODE', 'BIOKO-001'),
            facility_mode=app.config.get('FACILITY_MODE', 'local_server'),
            lan_url=app.config.get('LAN_URL', ''),
            now=datetime.utcnow,
        )

    return app
