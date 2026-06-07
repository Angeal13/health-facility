"""
BIOKO HEALTH — Nodo Provincial
================================
Activo cuando FACILITY_MODE = 'provincial_node'

Responsabilidades:
  1. Recibir y almacenar datos de todas las instalaciones de la provincia
  2. Servir expedientes a instalaciones que los solicitan (intranet)
  3. Dashboard de epidemiología provincial (solo lectura para el Ministerio)
  4. Enrutar solicitudes inter-provinciales (internet, bajo demanda)
  5. Cachear temporalmente expedientes de otras provincias

Flujo de solicitud de expediente:
  - Misma provincia:
      Instalación → GET /provincial/expediente/{uuid}
      → nodo devuelve expediente directamente
  - Otra provincia:
      Instalación → POST /provincial/solicitar-expediente
      → nodo llama al nodo de la otra provincia
      → recibe y cachea el expediente
      → lo sirve a la instalación
"""
import json
import logging
import requests
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, render_template, jsonify, request, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from app.models.models import (db, Paciente, Consulta, Diagnostico, Enfermedad,
                                Instalacion, Provincia, SolicitudExpediente,
                                CacheExpediente, TransferenciaPaciente, AlertaEpidemiologica,
                                Distrito, Vacuna, Prescripcion, ConsultaSintoma)

log = logging.getLogger('bioko.provincial')

provincial_bp = Blueprint('provincial', __name__)

# ─────────────────────────────────────────────────────────────────────────────
# DECORATOR — solo nodos provinciales y el servidor central pueden acceder
# ─────────────────────────────────────────────────────────────────────────────

def solo_nodo_o_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        mode = current_app.config.get('FACILITY_MODE', '')
        if not current_user.is_authenticated:
            abort(401)
        if mode not in ('provincial_node', 'central_server', 'intranet_central', 'annobon_node'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def requiere_token_provincial(f):
    """Para llamadas entre nodos — autenticación por token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Bioko-Token', '')
        expected = current_app.config.get('SYNC_API_TOKEN', '')
        if not token or token != expected:
            return jsonify({'error': 'Token inválido'}), 401
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD PROVINCIAL — solo lectura, para operadores del Ministerio
# ─────────────────────────────────────────────────────────────────────────────

@provincial_bp.route('/dashboard')
@login_required
@solo_nodo_o_admin
def dashboard():
    """
    Dashboard epidemiológico de la provincia.
    Vista de solo lectura — operadores del Ministerio de Sanidad.
    """
    cfg = current_app.config
    provincia_codigo = cfg.get('FACILITY_CODE', '')
    dias = request.args.get('dias', 30, type=int)
    fecha_inicio = datetime.utcnow() - timedelta(days=dias)

    # Instalaciones en esta provincia
    instalaciones = Instalacion.query.filter_by(activa=True).all()

    # Estadísticas globales de la provincia
    total_pacientes     = Paciente.query.filter_by(activo=True).count()
    total_consultas     = Consulta.query.filter(
        Consulta.fecha_consulta >= fecha_inicio).count()

    # Alertas activas
    alertas = (AlertaEpidemiologica.query
               .filter_by(estado='activa')
               .order_by(AlertaEpidemiologica.nivel.desc(),
                         AlertaEpidemiologica.casos_detectados.desc())
               .all())

    # Top diagnósticos en la provincia
    top_diagnosticos = (
        db.session.query(
            Enfermedad.codigo_icd10,
            Enfermedad.nombre_es,
            Enfermedad.es_notificable,
            func.count(Diagnostico.id).label('total')
        )
        .join(Diagnostico).join(Consulta)
        .filter(Consulta.fecha_consulta >= fecha_inicio)
        .group_by(Enfermedad.id)
        .order_by(func.count(Diagnostico.id).desc())
        .limit(10).all()
    )

    # Casos por instalación
    casos_por_instalacion = (
        db.session.query(
            Consulta.instalacion_id,
            func.count(Consulta.id).label('consultas')
        )
        .filter(Consulta.fecha_consulta >= fecha_inicio)
        .group_by(Consulta.instalacion_id)
        .all()
    )
    mapa_casos = {r.instalacion_id: r.consultas for r in casos_por_instalacion}

    # Tendencia semanal (últimas 8 semanas)
    tendencia = []
    for semana in range(8, 0, -1):
        ini = datetime.utcnow() - timedelta(weeks=semana)
        fin = datetime.utcnow() - timedelta(weeks=semana-1)
        total = (db.session.query(func.count(Consulta.id))
                 .filter(Consulta.fecha_consulta.between(ini, fin))
                 .scalar()) or 0
        tendencia.append({'semana': f'S-{semana}', 'total': total,
                          'inicio': ini.strftime('%d/%m')})

    # Enfermedades notificables con casos nuevos
    notificables_activas = (
        db.session.query(
            Enfermedad.nombre_es,
            Enfermedad.codigo_icd10,
            func.count(Diagnostico.id).label('casos')
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

    # Solicitudes de expediente pendientes / recientes
    solicitudes_recientes = (
        SolicitudExpediente.query
        .order_by(SolicitudExpediente.creada_en.desc())
        .limit(10).all()
    )

    return render_template(
        'provincial/dashboard.html',
        instalaciones=instalaciones,
        total_pacientes=total_pacientes,
        total_consultas=total_consultas,
        alertas=alertas,
        top_diagnosticos=top_diagnosticos,
        mapa_casos=mapa_casos,
        tendencia=tendencia,
        notificables_activas=notificables_activas,
        solicitudes_recientes=solicitudes_recientes,
        provincia_codigo=provincia_codigo,
        dias=dias,
    )


# ─────────────────────────────────────────────────────────────────────────────
# API INTRA-PROVINCIAL — instalaciones solicitan expedientes
# ─────────────────────────────────────────────────────────────────────────────

@provincial_bp.route('/api/expediente/<string:paciente_uuid>')
@requiere_token_provincial
def servir_expediente(paciente_uuid):
    """
    Una instalación de esta provincia solicita el expediente de un paciente.
    Si el paciente está en esta provincia: devuelve directamente.
    Si está en otra provincia: enruta la solicitud (ver solicitar_inter_provincial).
    """
    # Buscar en esta provincia primero
    paciente = Paciente.query.filter_by(uuid=paciente_uuid, activo=True).first()

    if paciente:
        datos = _serializar_expediente_completo(paciente)
        return jsonify({'fuente': 'local', 'expediente': datos})

    # Buscar en caché de expedientes de otras provincias
    cache = (CacheExpediente.query
             .filter_by(paciente_uuid=paciente_uuid, activo=True)
             .first())
    if cache and not cache.expirado:
        return jsonify({
            'fuente': 'cache',
            'provincia_origen': cache.provincia_origen,
            'expira_en': cache.expira_en.isoformat(),
            'expediente': {
                'paciente': json.loads(cache.datos_paciente),
                'consultas': json.loads(cache.datos_consultas),
                'vacunas': json.loads(cache.datos_vacunas or '[]'),
            }
        })

    return jsonify({
        'error': 'no_encontrado',
        'mensaje': 'Paciente no registrado en esta provincia. '
                   'Use /api/solicitar-expediente para buscarlo en otras provincias.'
    }), 404


@provincial_bp.route('/api/solicitar-expediente', methods=['POST'])
@requiere_token_provincial
def solicitar_expediente_interprovincial():
    """
    Una instalación pide un expediente que NO está en esta provincia.
    El nodo provincial lo solicita al nodo de la provincia correcta,
    lo cachea localmente y lo devuelve a la instalación.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400

    paciente_uuid     = data.get('paciente_uuid') or data.get('numero_historia')
    instalacion_cod   = data.get('instalacion_codigo', '')
    motivo            = data.get('motivo', '')
    urgente           = data.get('urgente', False)
    provincia_destino = data.get('provincia_destino', '')

    cfg = current_app.config
    provincia_propia = cfg.get('FACILITY_CODE', '')

    # Crear registro de solicitud
    solicitud = SolicitudExpediente(
        instalacion_solicitante_codigo=instalacion_cod,
        provincia_solicitante=provincia_propia,
        provincia_origen=provincia_destino,
        paciente_uuid=paciente_uuid or '',
        motivo=motivo,
        urgente=urgente,
        estado='enviada'
    )
    db.session.add(solicitud)
    db.session.flush()

    # Obtener URL del nodo de la provincia destino
    prov_obj = Provincia.query.filter_by(codigo=provincia_destino).first()
    if not prov_obj or not prov_obj.nodo_url:
        solicitud.estado = 'error'
        db.session.commit()
        return jsonify({'error': f'Nodo de provincia {provincia_destino} no configurado'}), 404

    # Llamar al nodo de la otra provincia
    token = cfg.get('SYNC_API_TOKEN', '')
    headers = {'X-Bioko-Token': token, 'X-Provincia-Origen': provincia_propia}

    try:
        url = f"{prov_obj.nodo_url.rstrip('/')}/provincial/api/expediente/{paciente_uuid}"
        resp = requests.get(url, headers=headers, timeout=20)

        if resp.status_code == 404:
            solicitud.estado = 'no_encontrado'
            db.session.commit()
            return jsonify({'error': 'Paciente no encontrado en la provincia destino'}), 404

        if resp.status_code != 200:
            solicitud.estado = 'error'
            db.session.commit()
            return jsonify({'error': f'Nodo destino respondió HTTP {resp.status_code}'}), 502

        expediente = resp.json().get('expediente', {})
        dias_cache  = cfg.get('CACHE_EXPEDIENTE_DIAS', 30)

        # Cachear el expediente localmente
        cache = CacheExpediente(
            solicitud_id=solicitud.id,
            paciente_uuid=paciente_uuid,
            provincia_origen=provincia_destino,
            instalacion_origen=expediente.get('paciente', {}).get('instalacion_origen', ''),
            datos_paciente=json.dumps(expediente.get('paciente', {})),
            datos_consultas=json.dumps(expediente.get('consultas', [])),
            datos_vacunas=json.dumps(expediente.get('vacunas', [])),
            expira_en=datetime.utcnow() + timedelta(days=dias_cache)
        )
        db.session.add(cache)
        solicitud.estado     = 'entregada'
        solicitud.respondida_en = datetime.utcnow()
        solicitud.entregada_en  = datetime.utcnow()
        solicitud.expira_en     = cache.expira_en
        db.session.commit()

        log.info(f"Expediente {paciente_uuid} obtenido de provincia {provincia_destino} "
                 f"— cacheado {dias_cache} días")
        return jsonify({
            'fuente': f'provincia_{provincia_destino}',
            'cacheado_hasta': cache.expira_en.isoformat(),
            'expediente': expediente
        })

    except requests.exceptions.ConnectionError:
        solicitud.estado = 'error'
        solicitud.motivo = 'Sin conexión al nodo provincial destino'
        db.session.commit()
        return jsonify({'error': 'Sin conexión al nodo provincial destino'}), 503
    except requests.exceptions.Timeout:
        solicitud.estado = 'error'
        solicitud.motivo = 'Timeout al contactar nodo provincial destino'
        db.session.commit()
        return jsonify({'error': 'Timeout — el nodo destino no respondió'}), 504


# ─────────────────────────────────────────────────────────────────────────────
# API INTER-PROVINCIAL — nodos provinciales se llaman entre sí
# ─────────────────────────────────────────────────────────────────────────────

@provincial_bp.route('/api/transferencia/iniciar', methods=['POST'])
@requiere_token_provincial
def iniciar_transferencia():
    """
    Una instalación inicia la transferencia formal de un paciente
    a otra provincia. El expediente se copia PERMANENTEMENTE al destino.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400

    paciente = Paciente.query.filter_by(
        uuid=data.get('paciente_uuid'), activo=True
    ).first()
    if not paciente:
        return jsonify({'error': 'Paciente no encontrado'}), 404

    cfg = current_app.config
    provincia_propia   = cfg.get('FACILITY_CODE', '')
    provincia_destino  = data.get('provincia_destino', '')
    instalacion_destino = data.get('instalacion_destino_codigo', '')

    # Registrar la transferencia
    transferencia = TransferenciaPaciente(
        paciente_id=paciente.id,
        paciente_uuid=paciente.uuid,
        instalacion_origen_codigo=data.get('instalacion_origen_codigo', ''),
        provincia_origen=provincia_propia,
        instalacion_destino_codigo=instalacion_destino,
        provincia_destino=provincia_destino,
        motivo_clinico=data.get('motivo_clinico', ''),
        urgente=data.get('urgente', False),
        estado='en_transito',
        iniciada_en=datetime.utcnow()
    )
    db.session.add(transferencia)
    db.session.flush()

    # Obtener nodo destino
    prov_obj = Provincia.query.filter_by(codigo=provincia_destino).first()
    if not prov_obj or not prov_obj.nodo_url:
        transferencia.estado = 'error'
        db.session.commit()
        return jsonify({'error': f'Nodo de provincia {provincia_destino} no configurado'}), 404

    # Enviar expediente completo al nodo destino (copia permanente)
    expediente = _serializar_expediente_completo(paciente)
    token = cfg.get('SYNC_API_TOKEN', '')
    headers = {
        'Content-Type': 'application/json',
        'X-Bioko-Token': token,
        'X-Transferencia-UUID': transferencia.uuid,
        'X-Provincia-Origen': provincia_propia,
    }

    try:
        url = f"{prov_obj.nodo_url.rstrip('/')}/provincial/api/recibir-transferencia"
        resp = requests.post(url, json={
            'expediente': expediente,
            'transferencia_uuid': transferencia.uuid,
            'instalacion_destino': instalacion_destino,
            'motivo_clinico': data.get('motivo_clinico', ''),
            'urgente': data.get('urgente', False),
        }, headers=headers, timeout=30)

        if resp.status_code == 200:
            transferencia.estado = 'confirmada'
            transferencia.confirmada_en = datetime.utcnow()
            db.session.commit()
            return jsonify({'ok': True, 'transferencia_uuid': transferencia.uuid,
                            'estado': 'confirmada'})
        else:
            transferencia.estado = 'error'
            db.session.commit()
            return jsonify({'error': f'Nodo destino rechazó: HTTP {resp.status_code}'}), 502

    except Exception as e:
        transferencia.estado = 'error'
        db.session.commit()
        return jsonify({'error': str(e)[:100]}), 503


@provincial_bp.route('/api/recibir-transferencia', methods=['POST'])
@requiere_token_provincial
def recibir_transferencia():
    """
    Este nodo provincial RECIBE un expediente de otra provincia.
    Importa el paciente y sus consultas de forma permanente.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400

    expediente         = data.get('expediente', {})
    transferencia_uuid = data.get('transferencia_uuid', '')
    instalacion_destino = data.get('instalacion_destino', '')

    try:
        resultado = _importar_expediente_permanente(expediente, instalacion_destino)
        log.info(f"Transferencia {transferencia_uuid} recibida — "
                 f"paciente {expediente.get('paciente', {}).get('uuid', '?')}")
        return jsonify({'ok': True, 'pacientes_importados': resultado})
    except Exception as e:
        log.error(f"Error recibiendo transferencia {transferencia_uuid}: {e}")
        return jsonify({'error': str(e)[:200]}), 500


# ─────────────────────────────────────────────────────────────────────────────
# API — Estado del nodo para monitoreo
# ─────────────────────────────────────────────────────────────────────────────

@provincial_bp.route('/api/estado')
@requiere_token_provincial
def estado_nodo():
    """Estado del nodo provincial — usado por el central y otros nodos."""
    cfg = current_app.config
    total_pats    = Paciente.query.filter_by(activo=True).count()
    total_consult = Consulta.query.count()
    alertas_act   = AlertaEpidemiologica.query.filter_by(estado='activa').count()
    instalaciones = Instalacion.query.filter_by(activa=True).count()

    return jsonify({
        'ok': True,
        'codigo': cfg.get('FACILITY_CODE'),
        'nombre': cfg.get('FACILITY_NAME'),
        'modo': cfg.get('FACILITY_MODE'),
        'timestamp': datetime.utcnow().isoformat(),
        'estadisticas': {
            'pacientes': total_pats,
            'consultas': total_consult,
            'alertas_activas': alertas_act,
            'instalaciones_conectadas': instalaciones,
        }
    })


# ─────────────────────────────────────────────────────────────────────────────
# SERIALIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def _serializar_expediente_completo(paciente) -> dict:
    """Serializa el expediente completo de un paciente para transferencia."""
    consultas = []
    for c in paciente.consultas.order_by(Consulta.fecha_consulta).all():
        consultas.append({
            'uuid': c.uuid,
            'fecha_consulta': c.fecha_consulta.isoformat(),
            'tipo': c.tipo,
            'motivo_consulta': c.motivo_consulta,
            'historia_enfermedad': c.historia_enfermedad,
            'examen_fisico': c.examen_fisico,
            'plan_tratamiento': c.plan_tratamiento,
            'temperatura': c.temperatura,
            'presion_sistolica': c.presion_sistolica,
            'presion_diastolica': c.presion_diastolica,
            'frecuencia_cardiaca': c.frecuencia_cardiaca,
            'frecuencia_respiratoria': c.frecuencia_respiratoria,
            'saturacion_oxigeno': c.saturacion_oxigeno,
            'peso_kg': c.peso_kg,
            'talla_cm': c.talla_cm,
            'estado': c.estado,
            'instalacion_codigo': c.instalacion.codigo if c.instalacion else '',
            'medico_nombre': c.medico.nombre_completo if c.medico else '',
            'diagnosticos': [{'codigo_icd10': d.enfermedad.codigo_icd10,
                               'nombre': d.enfermedad.nombre_es,
                               'tipo': d.tipo, 'es_principal': d.es_principal}
                             for d in c.diagnosticos.all()],
            'prescripciones': [{'medicamento': r.medicamento, 'dosis': r.dosis,
                                 'via': r.via, 'frecuencia': r.frecuencia,
                                 'duracion_dias': r.duracion_dias}
                               for r in c.medicamentos.all()],
        })

    vacunas = [{'nombre_vacuna': v.nombre_vacuna,
                'fecha_aplicacion': v.fecha_aplicacion.isoformat(),
                'dosis_numero': v.dosis_numero, 'lote': v.lote}
               for v in paciente.vacunas.all()]

    return {
        'paciente': {
            'uuid': paciente.uuid,
            'numero_historia': paciente.numero_historia,
            'dni': paciente.dni,
            'nombres': paciente.nombres,
            'apellidos': paciente.apellidos,
            'fecha_nacimiento': paciente.fecha_nacimiento.isoformat(),
            'sexo': paciente.sexo,
            'telefono': paciente.telefono,
            'grupo_sanguineo': paciente.grupo_sanguineo,
            'alergias': paciente.alergias,
            'condiciones_cronicas': paciente.condiciones_cronicas,
            'distrito_codigo': paciente.distrito.codigo if paciente.distrito else None,
            'instalacion_origen': (paciente.instalacion_origen.codigo
                                   if paciente.instalacion_origen_id else None),
        },
        'consultas': consultas,
        'vacunas': vacunas,
    }


def _importar_expediente_permanente(expediente: dict,
                                     instalacion_destino_codigo: str) -> int:
    """Importa un expediente recibido de otra provincia de forma permanente."""
    from app.models.models import Distrito, Instalacion, Enfermedad

    datos_p     = expediente.get('paciente', {})
    consultas_d = expediente.get('consultas', [])
    vacunas_d   = expediente.get('vacunas', [])

    # Verificar que no exista ya
    existente = Paciente.query.filter_by(uuid=datos_p.get('uuid')).first()
    if existente:
        return 0  # Ya existe, no duplicar

    from datetime import date
    fecha_nac = datetime.strptime(datos_p['fecha_nacimiento'], '%Y-%m-%d').date()

    inst_dest = Instalacion.query.filter_by(codigo=instalacion_destino_codigo).first()

    paciente = Paciente(
        uuid=datos_p['uuid'],
        numero_historia=datos_p.get('numero_historia', datos_p['uuid'][:12]),
        dni=datos_p.get('dni'),
        nombres=datos_p['nombres'],
        apellidos=datos_p['apellidos'],
        fecha_nacimiento=fecha_nac,
        sexo=datos_p['sexo'],
        telefono=datos_p.get('telefono'),
        grupo_sanguineo=datos_p.get('grupo_sanguineo'),
        alergias=datos_p.get('alergias'),
        condiciones_cronicas=datos_p.get('condiciones_cronicas'),
        instalacion_origen_id=inst_dest.id if inst_dest else None,
        sincronizado=True,
    )
    db.session.add(paciente)
    db.session.flush()

    # Importar consultas históricas
    for c_data in consultas_d:
        fecha = datetime.fromisoformat(c_data['fecha_consulta'])
        consulta = Consulta(
            uuid=c_data['uuid'],
            paciente_id=paciente.id,
            medico_id=1,
            instalacion_id=inst_dest.id if inst_dest else None,
            fecha_consulta=fecha,
            tipo=c_data.get('tipo', 'seguimiento'),
            motivo_consulta=c_data.get('motivo_consulta', ''),
            historia_enfermedad=c_data.get('historia_enfermedad'),
            examen_fisico=c_data.get('examen_fisico'),
            plan_tratamiento=c_data.get('plan_tratamiento'),
            temperatura=c_data.get('temperatura'),
            presion_sistolica=c_data.get('presion_sistolica'),
            presion_diastolica=c_data.get('presion_diastolica'),
            frecuencia_cardiaca=c_data.get('frecuencia_cardiaca'),
            saturacion_oxigeno=c_data.get('saturacion_oxigeno'),
            peso_kg=c_data.get('peso_kg'),
            talla_cm=c_data.get('talla_cm'),
            sincronizado=True,
        )
        db.session.add(consulta)
        db.session.flush()

        for d in c_data.get('diagnosticos', []):
            enf = Enfermedad.query.filter_by(codigo_icd10=d['codigo_icd10']).first()
            if enf:
                db.session.add(Diagnostico(
                    consulta_id=consulta.id,
                    enfermedad_id=enf.id,
                    tipo=d.get('tipo', 'definitivo'),
                    es_principal=d.get('es_principal', True)
                ))

    # Importar vacunas
    from datetime import date
    for v_data in vacunas_d:
        fecha_v = datetime.strptime(v_data['fecha_aplicacion'], '%Y-%m-%d').date()
        db.session.add(Vacuna(
            paciente_id=paciente.id,
            nombre_vacuna=v_data['nombre_vacuna'],
            fecha_aplicacion=fecha_v,
            dosis_numero=v_data.get('dosis_numero', 1),
            lote=v_data.get('lote'),
        ))

    db.session.commit()
    return 1
