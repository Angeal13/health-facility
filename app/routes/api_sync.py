"""
API de Sincronización: permite transferencia de datos entre clínicas locales
y el servidor central. Usa tokens de API para autenticación entre nodos.
"""
import hmac, hashlib, json
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from functools import wraps

from app.models.models import (db, Paciente, Consulta, Diagnostico, ConsultaSintoma,
                                Prescripcion, Enfermedad, Barrio, Distrito,
                                Instalacion, RegistroSync, AlertaEpidemiologica)

sync_bp = Blueprint('api_sync', __name__)


def requiere_api_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Bioko-Token')
        expected = current_app.config.get('SYNC_API_TOKEN', '')
        if not token or not hmac.compare_digest(token, expected):
            return jsonify({'error': 'Token inválido'}), 401
        return f(*args, **kwargs)
    return decorated


@sync_bp.route('/estado', methods=['GET'])
@requiere_api_token
def estado():
    """Verifica conectividad con el servidor central."""
    pendientes = RegistroSync.query.filter_by(estado='pendiente').count()
    return jsonify({
        'ok': True,
        'instalacion': current_app.config.get('FACILITY_CODE'),
        'nombre': current_app.config.get('FACILITY_NAME'),
        'timestamp': datetime.utcnow().isoformat(),
        'pendientes_sync': pendientes
    })


@sync_bp.route('/recibir-paciente', methods=['POST'])
@requiere_api_token
def recibir_paciente():
    """Recibe un paciente desde una clínica remota."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400

    # Verificar si ya existe por UUID
    existente = Paciente.query.filter_by(uuid=data.get('uuid')).first()
    if existente:
        return jsonify({'ok': True, 'accion': 'ya_existe', 'id': existente.id})

    # Verificar conflicto de DNI
    if data.get('dni'):
        conflicto = Paciente.query.filter_by(dni=data['dni']).first()
        if conflicto:
            return jsonify({
                'ok': False,
                'error': 'conflicto_dni',
                'paciente_existente_id': conflicto.id
            }), 409

    try:
        fecha_nac = datetime.strptime(data['fecha_nacimiento'], '%Y-%m-%d').date()
        paciente = Paciente(
            uuid=data['uuid'],
            numero_historia=_asignar_numero_historia(data['numero_historia']),
            dni=data.get('dni'),
            nombres=data['nombres'],
            apellidos=data['apellidos'],
            fecha_nacimiento=fecha_nac,
            sexo=data['sexo'],
            telefono=data.get('telefono'),
            distrito_id=_mapear_distrito(data.get('distrito_codigo')),
            barrio_id=_mapear_barrio(data.get('barrio_nombre'), data.get('distrito_codigo')),
            direccion=data.get('direccion'),
            etnia=data.get('etnia'),
            ocupacion=data.get('ocupacion'),
            grupo_sanguineo=data.get('grupo_sanguineo'),
            alergias=data.get('alergias'),
            condiciones_cronicas=data.get('condiciones_cronicas'),
            sincronizado=True,
        )
        db.session.add(paciente)
        db.session.commit()
        return jsonify({'ok': True, 'accion': 'creado', 'id': paciente.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/recibir-consulta', methods=['POST'])
@requiere_api_token
def recibir_consulta():
    """Recibe una consulta desde una clínica remota."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400

    existente = Consulta.query.filter_by(uuid=data.get('uuid')).first()
    if existente:
        return jsonify({'ok': True, 'accion': 'ya_existe'})

    paciente = Paciente.query.filter_by(uuid=data.get('paciente_uuid')).first()
    if not paciente:
        return jsonify({'error': 'paciente_no_encontrado'}), 404

    try:
        fecha = datetime.fromisoformat(data['fecha_consulta'])
        consulta = Consulta(
            uuid=data['uuid'],
            paciente_id=paciente.id,
            medico_id=1,  # Usuario sistema para datos recibidos
            instalacion_id=_mapear_instalacion(data.get('instalacion_codigo')),
            fecha_consulta=fecha,
            tipo=data.get('tipo', 'seguimiento'),
            motivo_consulta=data['motivo_consulta'],
            historia_enfermedad=data.get('historia_enfermedad'),
            examen_fisico=data.get('examen_fisico'),
            plan_tratamiento=data.get('plan_tratamiento'),
            temperatura=data.get('temperatura'),
            presion_sistolica=data.get('presion_sistolica'),
            presion_diastolica=data.get('presion_diastolica'),
            frecuencia_cardiaca=data.get('frecuencia_cardiaca'),
            peso_kg=data.get('peso_kg'),
            talla_cm=data.get('talla_cm'),
            sincronizado=True,
        )
        db.session.add(consulta)
        db.session.flush()

        # Diagnósticos
        for d in data.get('diagnosticos', []):
            enfermedad = Enfermedad.query.filter_by(codigo_icd10=d['codigo_icd10']).first()
            if enfermedad:
                diag = Diagnostico(
                    consulta_id=consulta.id,
                    enfermedad_id=enfermedad.id,
                    tipo=d.get('tipo', 'definitivo')
                )
                db.session.add(diag)

        db.session.commit()
        return jsonify({'ok': True, 'accion': 'creado', 'id': consulta.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/pendientes', methods=['GET'])
@requiere_api_token
def obtener_pendientes():
    """Lista registros pendientes de sincronizar (para clínicas locales)."""
    pendientes = RegistroSync.query.filter_by(estado='pendiente').limit(50).all()
    return jsonify([{
        'id': r.id,
        'tipo': r.tipo_dato,
        'uuid': r.uuid_registro,
        'accion': r.accion,
        'timestamp': r.timestamp.isoformat()
    } for r in pendientes])


@sync_bp.route('/marcar-enviado/<int:sync_id>', methods=['POST'])
@requiere_api_token
def marcar_enviado(sync_id):
    registro = RegistroSync.query.get_or_404(sync_id)
    registro.estado = 'enviado'
    db.session.commit()
    return jsonify({'ok': True})


# ─── Helpers ───────────────────────────────

def _asignar_numero_historia(historia_origen):
    """Asegura que el número de historia sea único en este nodo."""
    existente = Paciente.query.filter_by(numero_historia=historia_origen).first()
    if not existente:
        return historia_origen
    # Añadir sufijo del nodo para evitar colisión
    import random
    return f'{historia_origen}-R{random.randint(10,99)}'


def _mapear_distrito(codigo):
    if not codigo:
        return None
    d = Distrito.query.filter_by(codigo=codigo).first()
    return d.id if d else None


def _mapear_barrio(nombre, distrito_codigo):
    if not nombre or not distrito_codigo:
        return None
    distrito = Distrito.query.filter_by(codigo=distrito_codigo).first()
    if not distrito:
        return None
    b = Barrio.query.filter_by(nombre=nombre, distrito_id=distrito.id).first()
    return b.id if b else None


def _mapear_instalacion(codigo):
    if not codigo:
        return None
    i = Instalacion.query.filter_by(codigo=codigo).first()
    return i.id if i else None


# ─────────────────────────────────────────────
# REGISTRO DE NODOS (servidor central recibe)
# ─────────────────────────────────────────────

from app.models.models import NodoInstalacion  # noqa – añadido abajo en models


@sync_bp.route('/registrar-nodo', methods=['POST'])
@requiere_api_token
def registrar_nodo():
    """
    El servidor central recibe el registro de una instalación remota.
    Actualiza o crea el registro del nodo con su IP LAN y URL.
    """
    data = request.get_json()
    if not data or not data.get('codigo'):
        return jsonify({'error': 'Datos incompletos'}), 400

    nodo = NodoInstalacion.query.filter_by(codigo=data['codigo']).first()
    if nodo:
        nodo.nombre = data.get('nombre', nodo.nombre)
        nodo.tipo = data.get('tipo', nodo.tipo)
        nodo.ip_lan = data.get('ip_lan')
        nodo.puerto_lan = data.get('puerto_lan', 5000)
        nodo.lan_url = data.get('lan_url')
        nodo.hostname = data.get('hostname')
        nodo.ultimo_contacto = datetime.utcnow()
        nodo.estado = 'activo'
    else:
        nodo = NodoInstalacion(
            codigo=data['codigo'],
            nombre=data.get('nombre', data['codigo']),
            tipo=data.get('tipo', 'clinica'),
            ip_lan=data.get('ip_lan'),
            puerto_lan=data.get('puerto_lan', 5000),
            lan_url=data.get('lan_url'),
            hostname=data.get('hostname'),
            ultimo_contacto=datetime.utcnow(),
            estado='activo'
        )
        db.session.add(nodo)

    db.session.commit()
    return jsonify({'ok': True, 'mensaje': f'Nodo {data["codigo"]} registrado.'})


@sync_bp.route('/nodos', methods=['GET'])
@requiere_api_token
def listar_nodos():
    """Lista todos los nodos registrados con su estado."""
    nodos = NodoInstalacion.query.order_by(NodoInstalacion.nombre).all()
    return jsonify([{
        'codigo': n.codigo,
        'nombre': n.nombre,
        'tipo': n.tipo,
        'ip_lan': n.ip_lan,
        'lan_url': n.lan_url,
        'estado': n.estado,
        'ultimo_contacto': n.ultimo_contacto.isoformat() if n.ultimo_contacto else None,
    } for n in nodos])


# ─────────────────────────────────────────────────────────────────────────────
# INTRANET — endpoint de pull para nodos
# ─────────────────────────────────────────────────────────────────────────────

@sync_bp.route('/cambios-desde', methods=['GET'])
@requiere_api_token
def cambios_desde():
    """
    Devuelve todos los registros creados/modificados desde un timestamp dado.
    Usado por los nodos en modo intranet para descargar datos de otras
    instalaciones sin esperar el ciclo nocturno.

    Parámetros query:
        desde       ISO timestamp  (ej: 2026-05-23T10:00:00)
        instalacion Código del nodo solicitante (para excluir sus propios datos)
    """
    from app.models.models import Paciente, Consulta

    desde_str = request.args.get('desde', '2020-01-01T00:00:00')
    instalacion_origen = request.args.get('instalacion', '')

    try:
        desde_dt = datetime.fromisoformat(desde_str)
    except ValueError:
        desde_dt = datetime(2020, 1, 1)

    # Pacientes creados o modificados desde ese timestamp
    # Excluir los que ya pertenecen a esta instalación (ya los tiene)
    pacientes_query = Paciente.query.filter(
        Paciente.creado_en >= desde_dt
    )
    if instalacion_origen:
        instalacion_obj = Instalacion.query.filter_by(
            codigo=instalacion_origen
        ).first()
        if instalacion_obj:
            pacientes_query = pacientes_query.filter(
                Paciente.instalacion_origen_id != instalacion_obj.id
            )

    pacientes_nuevos = pacientes_query.limit(200).all()

    # Consultas nuevas de otras instalaciones
    consultas_query = Consulta.query.filter(
        Consulta.creado_en >= desde_dt
    )
    if instalacion_origen:
        instalacion_obj = Instalacion.query.filter_by(
            codigo=instalacion_origen
        ).first()
        if instalacion_obj:
            consultas_query = consultas_query.filter(
                Consulta.instalacion_id != instalacion_obj.id
            )

    consultas_nuevas = consultas_query.limit(500).all()

    return jsonify({
        'desde': desde_str,
        'timestamp_servidor': datetime.utcnow().isoformat(),
        'pacientes': [_serializar_paciente(p) for p in pacientes_nuevos],
        'consultas': [_serializar_consulta(c) for c in consultas_nuevas],
    })
