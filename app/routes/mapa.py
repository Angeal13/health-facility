from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from sqlalchemy import func
from datetime import datetime, timedelta

from app.models.models import (db, Paciente, Consulta, Diagnostico, Enfermedad,
                                Distrito, Barrio, Region, AlertaEpidemiologica)

mapa_bp = Blueprint('mapa', __name__)


@mapa_bp.route('/')
@login_required
def index():
    enfermedades = Enfermedad.query.filter_by(activa=True).order_by(Enfermedad.nombre_es).all()
    distritos = Distrito.query.all()
    return render_template('mapa/index.html',
                           enfermedades=enfermedades,
                           distritos=distritos)


@mapa_bp.route('/datos-calor')
@login_required
def datos_calor():
    """Datos para heatmap: casos por barrio con coordenadas."""
    dias = request.args.get('dias', 30, type=int)
    enfermedad_id = request.args.get('enfermedad_id', type=int)
    fecha_inicio = datetime.utcnow() - timedelta(days=dias)

    query = (
        db.session.query(
            Barrio.nombre.label('barrio'),
            Barrio.latitud,
            Barrio.longitud,
            Distrito.nombre.label('distrito'),
            func.count(Consulta.id).label('total')
        )
        .join(Paciente, Paciente.barrio_id == Barrio.id)
        .join(Consulta, Consulta.paciente_id == Paciente.id)
        .join(Distrito, Barrio.distrito_id == Distrito.id)
        .filter(
            Consulta.fecha_consulta >= fecha_inicio,
            Barrio.latitud.isnot(None)
        )
    )

    if enfermedad_id:
        query = (query.join(Diagnostico, Diagnostico.consulta_id == Consulta.id)
                 .filter(Diagnostico.enfermedad_id == enfermedad_id))

    datos = query.group_by(Barrio.id).all()

    # Formato: [[lat, lng, intensidad]]
    puntos = []
    for d in datos:
        if d.latitud and d.longitud and d.total > 0:
            puntos.append([d.latitud, d.longitud, d.total])

    return jsonify({
        'puntos': puntos,
        'total_casos': sum(p[2] for p in puntos)
    })


@mapa_bp.route('/distritos-geojson')
@login_required
def distritos_geojson():
    """Datos por distrito para coropleta."""
    dias = request.args.get('dias', 30, type=int)
    fecha_inicio = datetime.utcnow() - timedelta(days=dias)

    datos = (
        db.session.query(
            Distrito.id,
            Distrito.nombre,
            Distrito.latitud,
            Distrito.longitud,
            func.count(func.distinct(Paciente.id)).label('pacientes'),
            func.count(Consulta.id).label('consultas')
        )
        .outerjoin(Paciente, Paciente.distrito_id == Distrito.id)
        .outerjoin(Consulta, db.and_(
            Consulta.paciente_id == Paciente.id,
            Consulta.fecha_consulta >= fecha_inicio
        ))
        .group_by(Distrito.id)
        .all()
    )

    features = []
    for d in datos:
        if d.latitud and d.longitud:
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [d.longitud, d.latitud]},
                'properties': {
                    'id': d.id,
                    'nombre': d.nombre,
                    'pacientes': d.pacientes or 0,
                    'consultas': d.consultas or 0,
                }
            })

    return jsonify({'type': 'FeatureCollection', 'features': features})


@mapa_bp.route('/alertas-activas')
@login_required
def alertas_activas():
    alertas = (AlertaEpidemiologica.query
               .filter_by(estado='activa')
               .join(Distrito, isouter=True)
               .all())

    resultado = []
    for a in alertas:
        if a.distrito and a.distrito.latitud:
            resultado.append({
                'lat': a.distrito.latitud,
                'lng': a.distrito.longitud,
                'nivel': a.nivel,
                'enfermedad': a.enfermedad.nombre_es,
                'casos': a.casos_detectados,
                'distrito': a.distrito.nombre,
                'fecha': a.fecha_deteccion.strftime('%d/%m/%Y')
            })

    return jsonify(resultado)
