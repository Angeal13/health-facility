from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from datetime import datetime, date
import random, string

from app.models.models import (db, Paciente, Consulta, Diagnostico, Enfermedad,
                                Barrio, Distrito, Instalacion, RegistroSync)

pacientes_bp = Blueprint('pacientes', __name__)


def generar_numero_historia():
    """Genera número de historia clínica único: BK-YYYYNNNNN"""
    anio = datetime.now().year
    ultimo = Paciente.query.filter(
        Paciente.numero_historia.like(f'BK-{anio}%')
    ).count()
    return f'BK-{anio}{str(ultimo + 1).zfill(5)}'


@pacientes_bp.route('/dashboard')
@login_required
def dashboard():
    hoy = date.today()
    # Estadísticas del día
    consultas_hoy = Consulta.query.filter(
        func.date(Consulta.fecha_consulta) == hoy
    ).count()
    total_pacientes = Paciente.query.filter_by(activo=True).count()
    nuevos_hoy = Paciente.query.filter(
        func.date(Paciente.creado_en) == hoy
    ).count()

    # Últimas consultas
    ultimas_consultas = (Consulta.query
                         .join(Paciente)
                         .order_by(Consulta.fecha_consulta.desc())
                         .limit(10).all())

    # Alertas activas
    from app.models.models import AlertaEpidemiologica
    alertas = AlertaEpidemiologica.query.filter_by(estado='activa').order_by(
        AlertaEpidemiologica.fecha_deteccion.desc()
    ).limit(5).all()

    # Top enfermedades últimos 30 días
    from datetime import timedelta
    hace_30_dias = datetime.utcnow() - timedelta(days=30)
    top_enfermedades = (db.session.query(
        Enfermedad.nombre_es, func.count(Diagnostico.id).label('total')
    ).join(Diagnostico).join(Consulta)
     .filter(Consulta.fecha_consulta >= hace_30_dias)
     .group_by(Enfermedad.id)
     .order_by(func.count(Diagnostico.id).desc())
     .limit(5).all())

    return render_template('pacientes/dashboard.html',
                           consultas_hoy=consultas_hoy,
                           total_pacientes=total_pacientes,
                           nuevos_hoy=nuevos_hoy,
                           ultimas_consultas=ultimas_consultas,
                           alertas=alertas,
                           top_enfermedades=top_enfermedades)


@pacientes_bp.route('/')
@login_required
def lista():
    pagina = request.args.get('pagina', 1, type=int)
    busqueda = request.args.get('q', '').strip()
    distrito_id = request.args.get('distrito', type=int)

    query = Paciente.query.filter_by(activo=True)

    if busqueda:
        query = query.filter(or_(
            Paciente.nombres.ilike(f'%{busqueda}%'),
            Paciente.apellidos.ilike(f'%{busqueda}%'),
            Paciente.numero_historia.ilike(f'%{busqueda}%'),
            Paciente.dni.ilike(f'%{busqueda}%'),
        ))

    if distrito_id:
        query = query.filter_by(distrito_id=distrito_id)

    pacientes = query.order_by(Paciente.apellidos).paginate(
        page=pagina, per_page=25, error_out=False
    )
    distritos = Distrito.query.order_by(Distrito.nombre).all()

    return render_template('pacientes/lista.html',
                           pacientes=pacientes,
                           busqueda=busqueda,
                           distritos=distritos,
                           distrito_seleccionado=distrito_id)


@pacientes_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if request.method == 'POST':
        # Validar DNI único si se proporciona
        dni = request.form.get('dni', '').strip() or None
        if dni and Paciente.query.filter_by(dni=dni).first():
            flash('Ya existe un paciente con ese número de documento.', 'danger')
            return redirect(url_for('pacientes.nuevo'))

        fecha_nac_str = request.form.get('fecha_nacimiento')
        try:
            fecha_nac = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Fecha de nacimiento inválida.', 'danger')
            return redirect(url_for('pacientes.nuevo'))

        paciente = Paciente(
            numero_historia=generar_numero_historia(),
            dni=dni,
            nombres=request.form.get('nombres', '').strip(),
            apellidos=request.form.get('apellidos', '').strip(),
            fecha_nacimiento=fecha_nac,
            sexo=request.form.get('sexo'),
            telefono=request.form.get('telefono', '').strip() or None,
            barrio_id=request.form.get('barrio_id', type=int) or None,
            distrito_id=request.form.get('distrito_id', type=int) or None,
            direccion=request.form.get('direccion', '').strip() or None,
            etnia=request.form.get('etnia', '').strip() or None,
            ocupacion=request.form.get('ocupacion', '').strip() or None,
            grupo_sanguineo=request.form.get('grupo_sanguineo', '').strip() or None,
            alergias=request.form.get('alergias', '').strip() or None,
            condiciones_cronicas=request.form.get('condiciones_cronicas', '').strip() or None,
            creado_por_id=current_user.id,
            instalacion_origen_id=current_user.instalacion_id,
        )
        db.session.add(paciente)

        # Registrar para sync
        db.session.flush()
        sync = RegistroSync(
            instalacion_origen=current_user.instalacion.codigo if current_user.instalacion else 'LOCAL',
            tipo_dato='paciente',
            uuid_registro=paciente.uuid,
            accion='crear'
        )
        db.session.add(sync)
        db.session.commit()

        # Si estamos en modo intranet, propagar al central en tiempo real
        from flask import current_app
        if current_app.config.get('INTRANET_MODE'):
            from app.utils.intranet_sync import encolar_paciente
            encolar_paciente(paciente.uuid)

        flash(f'Paciente registrado con número de historia: {paciente.numero_historia}', 'success')
        return redirect(url_for('pacientes.ver', id=paciente.id))

    distritos = Distrito.query.order_by(Distrito.nombre).all()
    barrios = Barrio.query.order_by(Barrio.nombre).all()
    return render_template('pacientes/nuevo.html', distritos=distritos, barrios=barrios)


@pacientes_bp.route('/<int:id>')
@login_required
def ver(id):
    paciente = Paciente.query.get_or_404(id)
    consultas = (paciente.consultas
                 .order_by(Consulta.fecha_consulta.desc())
                 .limit(20).all())
    vacunas = paciente.vacunas.order_by('fecha_aplicacion').all()

    # Enfermedades únicas del paciente
    enfermedades_paciente = (db.session.query(Enfermedad)
                              .join(Diagnostico).join(Consulta)
                              .filter(Consulta.paciente_id == id)
                              .distinct().all())

    return render_template('pacientes/ver.html',
                           paciente=paciente,
                           consultas=consultas,
                           vacunas=vacunas,
                           enfermedades_paciente=enfermedades_paciente)


@pacientes_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    paciente = Paciente.query.get_or_404(id)

    if request.method == 'POST':
        fecha_nac_str = request.form.get('fecha_nacimiento')
        try:
            paciente.fecha_nacimiento = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Fecha de nacimiento inválida.', 'danger')
            return redirect(url_for('pacientes.editar', id=id))

        paciente.nombres = request.form.get('nombres', '').strip()
        paciente.apellidos = request.form.get('apellidos', '').strip()
        paciente.sexo = request.form.get('sexo')
        paciente.telefono = request.form.get('telefono', '').strip() or None
        paciente.barrio_id = request.form.get('barrio_id', type=int) or None
        paciente.distrito_id = request.form.get('distrito_id', type=int) or None
        paciente.direccion = request.form.get('direccion', '').strip() or None
        paciente.etnia = request.form.get('etnia', '').strip() or None
        paciente.ocupacion = request.form.get('ocupacion', '').strip() or None
        paciente.grupo_sanguineo = request.form.get('grupo_sanguineo', '').strip() or None
        paciente.alergias = request.form.get('alergias', '').strip() or None
        paciente.condiciones_cronicas = request.form.get('condiciones_cronicas', '').strip() or None
        paciente.sincronizado = False

        db.session.commit()
        flash('Datos del paciente actualizados.', 'success')
        return redirect(url_for('pacientes.ver', id=id))

    distritos = Distrito.query.order_by(Distrito.nombre).all()
    barrios = Barrio.query.order_by(Barrio.nombre).all()
    return render_template('pacientes/editar.html',
                           paciente=paciente,
                           distritos=distritos,
                           barrios=barrios)


@pacientes_bp.route('/buscar-ajax')
@login_required
def buscar_ajax():
    """Endpoint AJAX para búsqueda rápida en formularios de consulta."""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])

    pacientes = Paciente.query.filter(
        Paciente.activo == True,
        or_(
            Paciente.nombres.ilike(f'%{q}%'),
            Paciente.apellidos.ilike(f'%{q}%'),
            Paciente.numero_historia.ilike(f'%{q}%'),
            Paciente.dni.ilike(f'%{q}%'),
        )
    ).limit(10).all()

    return jsonify([{
        'id': p.id,
        'numero_historia': p.numero_historia,
        'nombre': p.nombre_completo,
        'edad': p.edad,
        'sexo': p.sexo,
        'dni': p.dni or '',
    } for p in pacientes])
