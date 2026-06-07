from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from app.models.models import (db, Consulta, Paciente, Diagnostico, ConsultaSintoma,
                                Prescripcion, ExamenLaboratorio, Enfermedad, Sintoma,
                                Instalacion, AlertaEpidemiologica, RegistroSync)

consultas_bp = Blueprint('consultas', __name__)


def verificar_umbral_alerta(enfermedad_id, distrito_id):
    """Verifica si hay un brote emergente para activar alerta automática."""
    from datetime import timedelta
    from flask import current_app
    from sqlalchemy import func
    hace_7_dias = datetime.utcnow() - timedelta(days=7)
    umbral = current_app.config.get('OUTBREAK_THRESHOLD', 5)

    casos = (db.session.query(func.count(Diagnostico.id))
             .join(Consulta).join(Paciente)
             .filter(
                 Diagnostico.enfermedad_id == enfermedad_id,
                 Consulta.fecha_consulta >= hace_7_dias,
                 Paciente.distrito_id == distrito_id
             ).scalar()) or 0

    if casos >= umbral:
        # Verificar si ya existe alerta activa
        existente = AlertaEpidemiologica.query.filter_by(
            enfermedad_id=enfermedad_id,
            distrito_id=distrito_id,
            estado='activa'
        ).first()

        if not existente:
            enfermedad = Enfermedad.query.get(enfermedad_id)
            nivel = 'emergencia' if casos >= umbral * 3 else 'alerta'
            alerta = AlertaEpidemiologica(
                enfermedad_id=enfermedad_id,
                distrito_id=distrito_id,
                nivel=nivel,
                casos_detectados=casos,
                descripcion=f'Detección automática: {casos} casos de {enfermedad.nombre_es} en 7 días.',
                creado_por_id=current_user.id
            )
            db.session.add(alerta)


@consultas_bp.route('/nueva', methods=['GET', 'POST'])
@consultas_bp.route('/nueva/<int:paciente_id>', methods=['GET', 'POST'])
@login_required
def nueva(paciente_id=None):
    paciente = None
    if paciente_id:
        paciente = Paciente.query.get_or_404(paciente_id)

    if request.method == 'POST':
        pid = request.form.get('paciente_id', type=int)
        paciente = Paciente.query.get_or_404(pid)

        consulta = Consulta(
            paciente_id=pid,
            medico_id=current_user.id,
            instalacion_id=current_user.instalacion_id,
            tipo=request.form.get('tipo', 'primera_vez'),
            motivo_consulta=request.form.get('motivo_consulta', '').strip(),
            historia_enfermedad=request.form.get('historia_enfermedad', '').strip() or None,
            examen_fisico=request.form.get('examen_fisico', '').strip() or None,
            plan_tratamiento=request.form.get('plan_tratamiento', '').strip() or None,
            observaciones=request.form.get('observaciones', '').strip() or None,
            # Signos vitales
            temperatura=_float_or_none(request.form.get('temperatura')),
            presion_sistolica=_int_or_none(request.form.get('presion_sistolica')),
            presion_diastolica=_int_or_none(request.form.get('presion_diastolica')),
            frecuencia_cardiaca=_int_or_none(request.form.get('frecuencia_cardiaca')),
            frecuencia_respiratoria=_int_or_none(request.form.get('frecuencia_respiratoria')),
            saturacion_oxigeno=_float_or_none(request.form.get('saturacion_oxigeno')),
            peso_kg=_float_or_none(request.form.get('peso_kg')),
            talla_cm=_float_or_none(request.form.get('talla_cm')),
        )
        db.session.add(consulta)
        db.session.flush()

        # Síntomas
        sintoma_ids = request.form.getlist('sintoma_ids[]')
        for sid in sintoma_ids:
            cs = ConsultaSintoma(
                consulta_id=consulta.id,
                sintoma_id=int(sid),
                intensidad=request.form.get(f'intensidad_{sid}', 'moderado'),
                duracion_dias=_int_or_none(request.form.get(f'duracion_{sid}')),
            )
            db.session.add(cs)

        # Diagnósticos
        enfermedad_ids = request.form.getlist('enfermedad_ids[]')
        for eid in enfermedad_ids:
            diag = Diagnostico(
                consulta_id=consulta.id,
                enfermedad_id=int(eid),
                tipo=request.form.get(f'tipo_diag_{eid}', 'definitivo'),
                es_principal=(eid == enfermedad_ids[0])
            )
            db.session.add(diag)

            # Verificar umbral de alerta
            if paciente.distrito_id:
                verificar_umbral_alerta(int(eid), paciente.distrito_id)

        # Prescripciones
        medicamentos = request.form.getlist('medicamento[]')
        dosis_list = request.form.getlist('dosis[]')
        vias = request.form.getlist('via[]')
        frecuencias = request.form.getlist('frecuencia[]')
        duraciones = request.form.getlist('duracion_dias[]')

        for i, med in enumerate(medicamentos):
            if med.strip():
                rx = Prescripcion(
                    consulta_id=consulta.id,
                    medicamento=med.strip(),
                    dosis=dosis_list[i] if i < len(dosis_list) else None,
                    via=vias[i] if i < len(vias) else None,
                    frecuencia=frecuencias[i] if i < len(frecuencias) else None,
                    duracion_dias=_int_or_none(duraciones[i]) if i < len(duraciones) else None,
                )
                db.session.add(rx)

        # Registro sync
        sync = RegistroSync(
            instalacion_origen=current_user.instalacion.codigo if current_user.instalacion else 'LOCAL',
            tipo_dato='consulta',
            uuid_registro=consulta.uuid,
            accion='crear'
        )
        db.session.add(sync)
        db.session.commit()

        # Intranet: propagar al central en tiempo real
        from flask import current_app
        if current_app.config.get('INTRANET_MODE'):
            from app.utils.intranet_sync import encolar_consulta
            encolar_consulta(consulta.uuid)

        flash('Consulta registrada correctamente.', 'success')
        return redirect(url_for('consultas.ver', id=consulta.id))

    sintomas = Sintoma.query.filter_by(activo=True).order_by(Sintoma.nombre_es).all()
    enfermedades = Enfermedad.query.filter_by(activa=True).order_by(Enfermedad.nombre_es).all()
    instalaciones = Instalacion.query.filter_by(activa=True).all()

    return render_template('consultas/nueva.html',
                           paciente=paciente,
                           sintomas=sintomas,
                           enfermedades=enfermedades,
                           instalaciones=instalaciones)


@consultas_bp.route('/<int:id>')
@login_required
def ver(id):
    consulta = Consulta.query.get_or_404(id)
    return render_template('consultas/ver.html', consulta=consulta)


@consultas_bp.route('/<int:id>/agregar-examen', methods=['POST'])
@login_required
def agregar_examen(id):
    consulta = Consulta.query.get_or_404(id)
    examen = ExamenLaboratorio(
        consulta_id=consulta.id,
        nombre_examen=request.form.get('nombre_examen', '').strip(),
        notas=request.form.get('notas', '').strip() or None,
    )
    db.session.add(examen)
    db.session.commit()
    flash('Examen de laboratorio agregado.', 'success')
    return redirect(url_for('consultas.ver', id=id))


@consultas_bp.route('/examen/<int:examen_id>/resultado', methods=['POST'])
@login_required
def cargar_resultado(examen_id):
    examen = ExamenLaboratorio.query.get_or_404(examen_id)
    examen.resultado = request.form.get('resultado', '').strip()
    examen.fecha_resultado = datetime.utcnow()
    examen.estado = 'completado'
    db.session.commit()
    flash('Resultado de laboratorio cargado.', 'success')
    return redirect(url_for('consultas.ver', id=examen.consulta_id))


@consultas_bp.route('/buscar-enfermedad')
@login_required
def buscar_enfermedad():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    enfermedades = Enfermedad.query.filter(
        Enfermedad.activa == True,
        db.or_(
            Enfermedad.nombre_es.ilike(f'%{q}%'),
            Enfermedad.codigo_icd10.ilike(f'%{q}%')
        )
    ).limit(10).all()
    return jsonify([{
        'id': e.id,
        'codigo': e.codigo_icd10,
        'nombre': e.nombre_es,
        'notificable': e.es_notificable
    } for e in enfermedades])


def _float_or_none(val):
    try:
        return float(val) if val and str(val).strip() else None
    except (ValueError, TypeError):
        return None


def _int_or_none(val):
    try:
        return int(val) if val and str(val).strip() else None
    except (ValueError, TypeError):
        return None
