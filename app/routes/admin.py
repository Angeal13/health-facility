from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models.models import (db, Usuario, Instalacion, Distrito, Barrio,
                                Enfermedad, Sintoma, Region)

admin_bp = Blueprint('admin', __name__)


def solo_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.es_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@solo_admin
def panel():
    stats = {
        'usuarios': Usuario.query.filter_by(activo=True).count(),
        'instalaciones': Instalacion.query.filter_by(activa=True).count(),
        'enfermedades': Enfermedad.query.filter_by(activa=True).count(),
        'sintomas': Sintoma.query.filter_by(activo=True).count(),
    }
    return render_template('admin/panel.html', stats=stats)


# ─── USUARIOS ───────────────────────────────

@admin_bp.route('/usuarios')
@login_required
@solo_admin
def usuarios():
    usuarios = Usuario.query.order_by(Usuario.nombre_completo).all()
    return render_template('admin/usuarios.html', usuarios=usuarios)


@admin_bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
@solo_admin
def nuevo_usuario():
    if request.method == 'POST':
        if Usuario.query.filter_by(nombre_usuario=request.form['nombre_usuario']).first():
            flash('Ese nombre de usuario ya existe.', 'danger')
            return redirect(url_for('admin.nuevo_usuario'))

        u = Usuario(
            nombre_usuario=request.form['nombre_usuario'].strip(),
            nombre_completo=request.form['nombre_completo'].strip(),
            email=request.form.get('email', '').strip() or None,
            rol=request.form['rol'],
            instalacion_id=request.form.get('instalacion_id', type=int) or None,
        )
        u.set_password(request.form['password'])
        db.session.add(u)
        db.session.commit()
        flash(f'Usuario {u.nombre_usuario} creado correctamente.', 'success')
        return redirect(url_for('admin.usuarios'))

    instalaciones = Instalacion.query.filter_by(activa=True).all()
    roles = ['superadmin', 'admin', 'medico', 'enfermero', 'laboratorio', 'epidemiologia', 'recepcion']
    return render_template('admin/nuevo_usuario.html', instalaciones=instalaciones, roles=roles)


@admin_bp.route('/usuarios/<int:id>/toggle', methods=['POST'])
@login_required
@solo_admin
def toggle_usuario(id):
    u = Usuario.query.get_or_404(id)
    if u.id == current_user.id:
        flash('No puedes desactivar tu propio usuario.', 'warning')
    else:
        u.activo = not u.activo
        db.session.commit()
        estado = 'activado' if u.activo else 'desactivado'
        flash(f'Usuario {u.nombre_usuario} {estado}.', 'info')
    return redirect(url_for('admin.usuarios'))


# ─── INSTALACIONES ───────────────────────────

@admin_bp.route('/instalaciones')
@login_required
@solo_admin
def instalaciones():
    instalaciones = Instalacion.query.order_by(Instalacion.nombre).all()
    return render_template('admin/instalaciones.html', instalaciones=instalaciones)


@admin_bp.route('/instalaciones/nueva', methods=['GET', 'POST'])
@login_required
@solo_admin
def nueva_instalacion():
    if request.method == 'POST':
        inst = Instalacion(
            codigo=request.form['codigo'].strip().upper(),
            nombre=request.form['nombre'].strip(),
            tipo=request.form['tipo'],
            distrito_id=request.form.get('distrito_id', type=int) or None,
            latitud=_float(request.form.get('latitud')),
            longitud=_float(request.form.get('longitud')),
            telefono=request.form.get('telefono', '').strip() or None,
        )
        db.session.add(inst)
        db.session.commit()
        flash(f'Instalación {inst.nombre} registrada.', 'success')
        return redirect(url_for('admin.instalaciones'))

    distritos = Distrito.query.order_by(Distrito.nombre).all()
    tipos = ['hospital', 'clinica', 'puesto', 'laboratorio', 'farmacia']
    return render_template('admin/nueva_instalacion.html', distritos=distritos, tipos=tipos)


# ─── CATÁLOGO ICD-10 ─────────────────────────

@admin_bp.route('/enfermedades')
@login_required
@solo_admin
def catalogo_enfermedades():
    pagina = request.args.get('pagina', 1, type=int)
    q = request.args.get('q', '').strip()
    query = Enfermedad.query
    if q:
        query = query.filter(
            db.or_(Enfermedad.nombre_es.ilike(f'%{q}%'),
                   Enfermedad.codigo_icd10.ilike(f'%{q}%'))
        )
    enfermedades = query.order_by(Enfermedad.codigo_icd10).paginate(
        page=pagina, per_page=30, error_out=False
    )
    return render_template('admin/enfermedades.html', enfermedades=enfermedades, q=q)


def _float(val):
    try:
        return float(val) if val and str(val).strip() else None
    except (ValueError, TypeError):
        return None
