from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta

from app.models.models import (db, Enfermedad, Diagnostico, Consulta, Paciente,
                                AlertaEpidemiologica, Distrito, Barrio, Sintoma,
                                ConsultaSintoma)

enfermedades_bp = Blueprint('enfermedades', __name__)


@enfermedades_bp.route('/')
@login_required
def vigilancia():
    """Panel principal de vigilancia epidemiológica."""
    # Periodo seleccionado
    dias = request.args.get('dias', 30, type=int)
    fecha_inicio = datetime.utcnow() - timedelta(days=dias)

    # Casos por enfermedad
    casos_por_enfermedad = (
        db.session.query(
            Enfermedad.nombre_es,
            Enfermedad.codigo_icd10,
            Enfermedad.es_notificable,
            Enfermedad.es_tropical,
            func.count(Diagnostico.id).label('total')
        )
        .join(Diagnostico).join(Consulta)
        .filter(Consulta.fecha_consulta >= fecha_inicio)
        .group_by(Enfermedad.id)
        .order_by(func.count(Diagnostico.id).desc())
        .limit(20).all()
    )

    # Casos por distrito
    casos_por_distrito = (
        db.session.query(
            Distrito.nombre,
            func.count(Diagnostico.id).label('total')
        )
        .join(Paciente, Paciente.distrito_id == Distrito.id)
        .join(Consulta, Consulta.paciente_id == Paciente.id)
        .join(Diagnostico, Diagnostico.consulta_id == Consulta.id)
        .filter(Consulta.fecha_consulta >= fecha_inicio)
        .group_by(Distrito.id)
        .order_by(func.count(Diagnostico.id).desc())
        .all()
    )

    # Tendencia semanal (últimas 8 semanas)
    tendencia = []
    for semana in range(8, 0, -1):
        inicio_semana = datetime.utcnow() - timedelta(weeks=semana)
        fin_semana = datetime.utcnow() - timedelta(weeks=semana - 1)
        total = (db.session.query(func.count(Consulta.id))
                 .filter(Consulta.fecha_consulta >= inicio_semana,
                         Consulta.fecha_consulta < fin_semana)
                 .scalar()) or 0
        tendencia.append({
            'semana': f'S-{semana}',
            'total': total,
            'inicio': inicio_semana.strftime('%d/%m')
        })

    # Alertas activas
    alertas = (AlertaEpidemiologica.query
               .filter_by(estado='activa')
               .order_by(AlertaEpidemiologica.fecha_deteccion.desc())
               .all())

    # Enfermedades notificables con casos
    notificables = (
        db.session.query(
            Enfermedad.nombre_es,
            Enfermedad.codigo_icd10,
            func.count(Diagnostico.id).label('total')
        )
        .join(Diagnostico).join(Consulta)
        .filter(
            Enfermedad.es_notificable == True,
            Consulta.fecha_consulta >= fecha_inicio
        )
        .group_by(Enfermedad.id)
        .order_by(func.count(Diagnostico.id).desc())
        .all()
    )

    return render_template('enfermedades/vigilancia.html',
                           casos_por_enfermedad=casos_por_enfermedad,
                           casos_por_distrito=casos_por_distrito,
                           tendencia=tendencia,
                           alertas=alertas,
                           notificables=notificables,
                           dias=dias)


@enfermedades_bp.route('/datos-mapa')
@login_required
def datos_mapa():
    """GeoJSON para el mapa de dispersión de enfermedades."""
    dias = request.args.get('dias', 30, type=int)
    enfermedad_id = request.args.get('enfermedad_id', type=int)
    fecha_inicio = datetime.utcnow() - timedelta(days=dias)

    query = (
        db.session.query(
            Distrito.nombre.label('distrito'),
            Distrito.latitud,
            Distrito.longitud,
            func.count(Diagnostico.id).label('total')
        )
        .join(Paciente, Paciente.distrito_id == Distrito.id)
        .join(Consulta, Consulta.paciente_id == Paciente.id)
        .join(Diagnostico, Diagnostico.consulta_id == Consulta.id)
        .filter(
            Consulta.fecha_consulta >= fecha_inicio,
            Distrito.latitud.isnot(None)
        )
    )

    if enfermedad_id:
        query = query.filter(Diagnostico.enfermedad_id == enfermedad_id)

    datos = query.group_by(Distrito.id).all()

    features = []
    for d in datos:
        if d.latitud and d.longitud:
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [d.longitud, d.latitud]
                },
                'properties': {
                    'nombre': d.distrito,
                    'casos': d.total
                }
            })

    return jsonify({'type': 'FeatureCollection', 'features': features})


@enfermedades_bp.route('/sintomas-frecuentes')
@login_required
def sintomas_frecuentes():
    """Top síntomas en el periodo."""
    dias = request.args.get('dias', 30, type=int)
    fecha_inicio = datetime.utcnow() - timedelta(days=dias)

    datos = (
        db.session.query(
            Sintoma.nombre_es,
            Sintoma.categoria,
            func.count(ConsultaSintoma.id).label('total')
        )
        .join(ConsultaSintoma).join(Consulta)
        .filter(Consulta.fecha_consulta >= fecha_inicio)
        .group_by(Sintoma.id)
        .order_by(func.count(ConsultaSintoma.id).desc())
        .limit(15).all()
    )

    return jsonify([{
        'sintoma': d.nombre_es,
        'categoria': d.categoria,
        'total': d.total
    } for d in datos])


@enfermedades_bp.route('/alerta/<int:id>/resolver', methods=['POST'])
@login_required
def resolver_alerta(id):
    alerta = AlertaEpidemiologica.query.get_or_404(id)
    alerta.estado = 'resuelta'
    alerta.resuelta_en = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})
