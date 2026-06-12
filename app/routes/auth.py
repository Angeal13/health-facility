"""
BIOKO HEALTH — Autenticación
=============================
Seguridad:
  - Rate limiting en login (10 intentos/minuto por IP) contra fuerza bruta
  - Validación de redirect 'next' contra open redirect
  - Timeout de sesión por inactividad (8 horas)
  - Passwords con bcrypt (en models.py)
"""
from urllib.parse import urlparse, urljoin

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, session, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from functools import wraps

from app.models.models import db, Usuario
from app.extensions import limiter

auth_bp = Blueprint('auth', __name__)

SESSION_TIMEOUT_MINUTES = 480  # 8 horas


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES DE SEGURIDAD
# ─────────────────────────────────────────────────────────────────────────────

def es_url_segura(target: str) -> bool:
    """
    Valida que la URL de redirección sea interna (mismo host).
    Previene ataques de open redirect: /login?next=https://malicioso.com
    """
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return (test_url.scheme in ('http', 'https')
            and ref_url.netloc == test_url.netloc)


def check_session_timeout(f):
    """Expira la sesión tras inactividad prolongada."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.is_authenticated:
            last_active = session.get('last_active')
            now = datetime.utcnow()
            if last_active:
                last_dt = datetime.fromisoformat(last_active)
                if (now - last_dt).total_seconds() > SESSION_TIMEOUT_MINUTES * 60:
                    logout_user()
                    flash('Sesión expirada por inactividad. Por favor inicia sesión de nuevo.', 'warning')
                    return redirect(url_for('auth.login'))
            session['last_active'] = now.isoformat()
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# RUTAS
# ─────────────────────────────────────────────────────────────────────────────

def _login_limit():
    """Límite configurable vía LOGIN_RATE_LIMIT en .env (defecto: 10/min)."""
    from flask import current_app
    return current_app.config.get('LOGIN_RATE_LIMIT', '10 per minute')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(_login_limit, methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('pacientes.dashboard'))

    if request.method == 'POST':
        # Rate limiting aplicado dinámicamente (ver _aplicar_rate_limit abajo)
        nombre_usuario = request.form.get('nombre_usuario', '').strip()
        password = request.form.get('password', '')

        usuario = Usuario.query.filter_by(
            nombre_usuario=nombre_usuario, activo=True
        ).first()

        if usuario and usuario.check_password(password):
            login_user(usuario, remember=bool(request.form.get('recordar')))
            usuario.ultimo_acceso = datetime.utcnow()
            db.session.commit()
            session['last_active'] = datetime.utcnow().isoformat()

            # FIX SEGURIDAD: validar 'next' contra open redirect
            next_page = request.args.get('next')
            if next_page and es_url_segura(next_page):
                return redirect(next_page)
            return redirect(url_for('pacientes.dashboard'))
        else:
            current_app.logger.warning(
                f"Intento de login fallido para usuario '{nombre_usuario}' "
                f"desde IP {request.remote_addr}"
            )
            flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('last_active', None)
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/cambiar-password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    if request.method == 'POST':
        password_actual = request.form.get('password_actual', '')
        password_nueva = request.form.get('password_nueva', '')
        password_confirmar = request.form.get('password_confirmar', '')

        if not current_user.check_password(password_actual):
            flash('La contraseña actual es incorrecta.', 'danger')
        elif password_nueva != password_confirmar:
            flash('Las contraseñas nuevas no coinciden.', 'danger')
        elif len(password_nueva) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'danger')
        else:
            current_user.set_password(password_nueva)
            db.session.commit()
            flash('Contraseña actualizada correctamente.', 'success')
            return redirect(url_for('pacientes.dashboard'))

    return render_template('auth/cambiar_password.html')

