"""
Red de Instalaciones — Bioko Health
Gestiona:
  - Panel de red LAN de cada instalación
  - Registro de nodos con el servidor central
  - Estado de conectividad de nodos remotos (para el servidor central)
  - Instrucciones para conectar nuevos PCs a la LAN
"""
import socket
import requests
from flask import Blueprint, render_template, jsonify, request, current_app, abort
from flask_login import login_required, current_user
from datetime import datetime

from app.models.models import db, Instalacion, RegistroSync

red_bp = Blueprint('red', __name__)


# ─────────────────────────────────────────────
# HELPERS DE RED
# ─────────────────────────────────────────────

def _obtener_ip_local():
    """Obtiene la IP de esta máquina en la red local."""
    try:
        # Conectar a un destino externo (sin enviar datos) para descubrir la IP local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return '127.0.0.1'


def _obtener_hostname():
    try:
        return socket.gethostname()
    except Exception:
        return 'desconocido'


def _verificar_central():
    """Intenta contactar el servidor central. Retorna dict con resultado."""
    url = current_app.config.get('CENTRAL_SERVER_URL', '').rstrip('/')
    token = current_app.config.get('SYNC_API_TOKEN', '')
    if not url:
        return {'disponible': False, 'razon': 'No configurado'}
    try:
        resp = requests.get(
            f'{url}/api/sync/estado',
            headers={'X-Bioko-Token': token},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return {'disponible': True, 'instalacion': data.get('nombre'), 'url': url}
        return {'disponible': False, 'razon': f'HTTP {resp.status_code}', 'url': url}
    except requests.exceptions.ConnectionError:
        return {'disponible': False, 'razon': 'Sin conexión', 'url': url}
    except requests.exceptions.Timeout:
        return {'disponible': False, 'razon': 'Timeout (>5s)', 'url': url}
    except Exception as e:
        return {'disponible': False, 'razon': str(e)[:60], 'url': url}


# ─────────────────────────────────────────────
# PANEL DE RED
# ─────────────────────────────────────────────

@red_bp.route('/')
@login_required
def panel():
    """Panel principal de red — visible para admins."""
    if not current_user.es_admin:
        abort(403)

    cfg = current_app.config
    ip_local = _obtener_ip_local()
    hostname = _obtener_hostname()
    port = cfg.get('LAN_PORT', 5000)
    lan_url = cfg.get('LAN_URL') or f'http://{ip_local}:{port}'
    modo = cfg.get('FACILITY_MODE', 'local_server')

    # Estado del servidor central
    estado_central = None
    if cfg.get('SYNC_ENABLED'):
        estado_central = _verificar_central()

    # Estadísticas de sync
    pendientes = RegistroSync.query.filter_by(estado='pendiente').count()
    errores = RegistroSync.query.filter_by(estado='error').count()
    conflictos = RegistroSync.query.filter_by(estado='conflicto').count()

    # Todas las instalaciones registradas (para el servidor central)
    instalaciones = Instalacion.query.filter_by(activa=True).order_by(Instalacion.nombre).all()

    return render_template('red/panel.html',
                           ip_local=ip_local,
                           hostname=hostname,
                           port=port,
                           lan_url=lan_url,
                           modo=modo,
                           estado_central=estado_central,
                           pendientes=pendientes,
                           errores=errores,
                           conflictos=conflictos,
                           instalaciones=instalaciones,
                           sync_habilitado=cfg.get('SYNC_ENABLED', False),
                           central_url=cfg.get('CENTRAL_SERVER_URL', ''))


@red_bp.route('/estado-json')
@login_required
def estado_json():
    """Estado resumido en JSON — para polling desde la UI."""
    ip_local = _obtener_ip_local()
    port = current_app.config.get('LAN_PORT', 5000)
    lan_url = current_app.config.get('LAN_URL') or f'http://{ip_local}:{port}'

    central = None
    if current_app.config.get('SYNC_ENABLED'):
        central = _verificar_central()

    pendientes = RegistroSync.query.filter_by(estado='pendiente').count()

    return jsonify({
        'ip_local': ip_local,
        'hostname': _obtener_hostname(),
        'lan_url': lan_url,
        'modo': current_app.config.get('FACILITY_MODE', 'local_server'),
        'central': central,
        'pendientes_sync': pendientes,
        'timestamp': datetime.utcnow().isoformat()
    })


@red_bp.route('/verificar-central')
@login_required
def verificar_central_ajax():
    """Verificación de conectividad bajo demanda (AJAX)."""
    if not current_user.es_admin:
        abort(403)
    resultado = _verificar_central()
    return jsonify(resultado)


@red_bp.route('/registrar-nodo', methods=['POST'])
@login_required
def registrar_nodo():
    """
    Registra esta instalación con el servidor central.
    Envía: código, nombre, tipo, IP local, URL LAN.
    El servidor central guarda los datos para el panel de topología.
    """
    if not current_user.es_admin:
        abort(403)

    cfg = current_app.config
    url_central = cfg.get('CENTRAL_SERVER_URL', '').rstrip('/')
    token = cfg.get('SYNC_API_TOKEN', '')

    if not url_central:
        return jsonify({'ok': False, 'error': 'Servidor central no configurado'})

    ip = _obtener_ip_local()
    port = cfg.get('LAN_PORT', 5000)
    lan_url = cfg.get('LAN_URL') or f'http://{ip}:{port}'

    payload = {
        'codigo': cfg.get('FACILITY_CODE'),
        'nombre': cfg.get('FACILITY_NAME'),
        'tipo': cfg.get('FACILITY_TYPE'),
        'ip_lan': ip,
        'puerto_lan': port,
        'lan_url': lan_url,
        'hostname': _obtener_hostname(),
        'version': '1.0',
        'timestamp': datetime.utcnow().isoformat()
    }

    try:
        resp = requests.post(
            f'{url_central}/api/sync/registrar-nodo',
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Bioko-Token': token
            },
            timeout=10
        )
        if resp.status_code == 200:
            return jsonify({'ok': True, 'mensaje': 'Nodo registrado correctamente.'})
        return jsonify({'ok': False, 'error': f'HTTP {resp.status_code}'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)[:100]})
