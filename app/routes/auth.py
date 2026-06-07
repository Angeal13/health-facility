from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from functools import wraps
from app.models.models import db, Usuario

auth_bp = Blueprint('auth', __name__)



SESSION_TIMEOUT_MINUTES = 480  # 8 hours

def check_session_timeout(f):
    """Expire session after inactivity."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.is_authenticated:
            last_active = session.get('last_active')
            now = datetime.utcnow()
            if last_active:
                from datetime import datetime as dt
                last_dt = dt.fromisoformat(last_active)
                if (now - last_dt).total_seconds() > SESSION_TIMEOUT_MINUTES * 60:
                    logout_user()
                    flash('Sesión expirada por inactividad. Por favor inicia sesión de nuevo.', 'warning')
                    return redirect(url_for('auth.login'))
            session['last_active'] = now.isoformat()
        return f(*args, **kwargs)
    return decorated

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('pacientes.dashboard'))

    if request.method == 'POST':
        nombre_usuario = request.form.get('nombre_usuario', '').strip()
        password = request.form.get('password', '')

        usuario = Usuario.query.filter_by(
            nombre_usuario=nombre_usuario, activo=True
        ).first()

        if usuario and usuario.check_password(password):
            login_user(usuario, remember=request.form.get('recordar'))
            usuario.ultimo_acceso = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get('next')
            return redirect(next_page or url_for('pacientes.dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
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
