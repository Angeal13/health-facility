"""
BIOKO HEALTH — Motor de Sincronización en Tiempo Real (Intranet)
================================================================
Activo cuando INTRANET_MODE=true.

Comportamiento:
  - Cada escritura (paciente, consulta) se propaga al servidor central
    en segundos mediante una cola de tareas en background.
  - Si el enlace troncal de la isla cae, los registros se acumulan
    en la cola local y se reenvían en cuanto se restablece.
  - Un hilo de "pull" descarga cambios del central periódicamente,
    permitiendo que los nodos vean datos de otras instalaciones
    sin esperar al ciclo nocturno.
  - Compatible con el sync periódico existente — ambos pueden correr
    simultáneamente; el intranet sync simplemente es mucho más frecuente.
"""
import logging
import threading
import requests
import json
from datetime import datetime
from queue import Queue, Empty
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger('bioko.intranet')

# ─────────────────────────────────────────────────────────────────────────────
# COLA DE ESCRITURAS PENDIENTES (en memoria + BD como respaldo)
# ─────────────────────────────────────────────────────────────────────────────
_write_queue: Queue = Queue()
_link_healthy: bool = True          # Estado del enlace al central
_lock = threading.Lock()


def marcar_enlace(sano: bool):
    global _link_healthy
    with _lock:
        if _link_healthy != sano:
            _link_healthy = sano
            estado = "DISPONIBLE" if sano else "CAÍDO"
            log.warning(f"Enlace intranet → servidor central: {estado}")


# ─────────────────────────────────────────────────────────────────────────────
# API DE USO PÚBLICO — llamada desde las rutas cuando INTRANET_MODE=True
# ─────────────────────────────────────────────────────────────────────────────

def encolar_paciente(paciente_uuid: str):
    """Encola la propagación de un paciente al servidor central."""
    _write_queue.put({'tipo': 'paciente', 'uuid': paciente_uuid,
                      'ts': datetime.utcnow().isoformat()})


def encolar_consulta(consulta_uuid: str):
    """Encola la propagación de una consulta al servidor central."""
    _write_queue.put({'tipo': 'consulta', 'uuid': consulta_uuid,
                      'ts': datetime.utcnow().isoformat()})


def enlace_disponible() -> bool:
    """Devuelve True si el último intento de contacto al central fue exitoso."""
    return _link_healthy


# ─────────────────────────────────────────────────────────────────────────────
# CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class IntranetSyncEngine:
    """
    Motor de sync para la intranet de Bioko.

    Dos hilos independientes:
      1. PUSH worker  — consume la cola de escrituras y las envía al central.
      2. PULL scheduler — descarga cambios recientes del central periódicamente.
    """

    def __init__(self, app):
        self.app = app
        self.scheduler = BackgroundScheduler(timezone='Africa/Malabo')
        self._push_thread = None
        self._running = False

    # ── Inicio / Parada ──────────────────────────────────────────────────────

    def iniciar(self):
        cfg = self.app.config
        if not cfg.get('INTRANET_MODE'):
            return
        if not cfg.get('INTRANET_CENTRAL_URL') and not cfg.get('CENTRAL_SERVER_URL'):
            log.warning("INTRANET_MODE=true pero INTRANET_CENTRAL_URL no configurado. "
                        "Intranet sync desactivado.")
            return

        self._running = True

        # Hilo PUSH — consume la cola continuamente
        self._push_thread = threading.Thread(
            target=self._push_worker, daemon=True, name='bioko-intranet-push'
        )
        self._push_thread.start()

        # Scheduler PULL — descarga cambios del central
        pull_interval = cfg.get('INTRANET_PULL_INTERVAL', 30)
        self.scheduler.add_job(
            func=self._pull_desde_central,
            trigger=IntervalTrigger(seconds=pull_interval),
            id='intranet_pull',
            name=f'Pull desde central cada {pull_interval}s',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        # También reenviar pendientes de la BD cada minuto (por si el proceso reinició)
        self.scheduler.add_job(
            func=self._reencolar_pendientes_bd,
            trigger=IntervalTrigger(minutes=1),
            id='intranet_reencolar',
            name='Reencolar registros BD pendientes',
            replace_existing=True,
            max_instances=1,
        )

        self.scheduler.start()
        log.info(f"Intranet sync activo — pull cada {pull_interval}s — "
                 f"push en tiempo real")

    def detener(self):
        self._running = False
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    # ── PUSH worker ──────────────────────────────────────────────────────────

    def _push_worker(self):
        """
        Corre en un hilo dedicado.
        Extrae items de la cola y los envía al central.
        Si el envío falla, el item vuelve a la cola después de un breve delay.
        """
        retry_interval = self.app.config.get('INTRANET_RETRY_INTERVAL', 10)

        while self._running:
            try:
                item = _write_queue.get(timeout=2)
            except Empty:
                continue

            with self.app.app_context():
                exito = self._enviar_item(item)
                if not exito:
                    # Devolver a la cola para reintento
                    _write_queue.put(item)
                    import time
                    time.sleep(retry_interval)

    def _enviar_item(self, item: dict) -> bool:
        """Envía un item al servidor central. Retorna True si tuvo éxito."""
        from app.models.models import db, Paciente, Consulta, RegistroSync
        from app.routes.api_sync import _serializar_paciente, _serializar_consulta

        cfg = self.app.config
        url_base = (cfg.get('INTRANET_CENTRAL_URL') or
                    cfg.get('CENTRAL_SERVER_URL', '')).rstrip('/')
        token = cfg.get('SYNC_API_TOKEN', '')
        headers = {
            'Content-Type': 'application/json',
            'X-Bioko-Token': token,
            'X-Instalacion': cfg.get('FACILITY_CODE', 'UNKNOWN'),
            'X-Intranet': 'true',     # El central distingue intranet de internet
        }

        try:
            if item['tipo'] == 'paciente':
                obj = Paciente.query.filter_by(uuid=item['uuid']).first()
                if not obj:
                    return True   # Ya no existe, descartar
                payload = _serializar_paciente(obj)
                endpoint = f'{url_base}/api/sync/recibir-paciente'
            elif item['tipo'] == 'consulta':
                obj = Consulta.query.filter_by(uuid=item['uuid']).first()
                if not obj:
                    return True
                payload = _serializar_consulta(obj)
                endpoint = f'{url_base}/api/sync/recibir-consulta'
            else:
                return True   # Tipo desconocido, descartar

            resp = requests.post(endpoint, json=payload, headers=headers, timeout=8)

            if resp.status_code in (200, 201):
                marcar_enlace(True)
                # Marcar como sincronizado en la BD local
                obj.sincronizado = True
                db.session.commit()
                return True
            elif resp.status_code == 409:
                # Conflicto de DNI — no es un error de enlace, descartar para
                # revisión manual (ya queda en RegistroSync con estado='conflicto')
                marcar_enlace(True)
                return True
            else:
                log.warning(f"Intranet push: HTTP {resp.status_code} para {item}")
                marcar_enlace(False)
                return False

        except requests.exceptions.ConnectionError:
            marcar_enlace(False)
            return False
        except requests.exceptions.Timeout:
            marcar_enlace(False)
            return False
        except Exception as e:
            log.error(f"Intranet push error: {e}")
            return False

    # ── PULL desde central ───────────────────────────────────────────────────

    def _pull_desde_central(self):
        """
        Descarga del servidor central los registros nuevos o actualizados
        desde la última vez que este nodo hizo pull.
        Esto permite que un nodo vea datos de otras instalaciones.
        """
        with self.app.app_context():
            from app.models.models import db, Paciente, Consulta

            cfg = self.app.config
            url_base = (cfg.get('INTRANET_CENTRAL_URL') or
                        cfg.get('CENTRAL_SERVER_URL', '')).rstrip('/')
            token = cfg.get('SYNC_API_TOKEN', '')

            if not url_base:
                return

            # Leer el timestamp del último pull (guardado en un archivo local)
            ultimo_pull = self._leer_ultimo_pull()

            try:
                resp = requests.get(
                    f'{url_base}/api/sync/cambios-desde',
                    params={
                        'desde': ultimo_pull,
                        'instalacion': cfg.get('FACILITY_CODE'),
                    },
                    headers={'X-Bioko-Token': token, 'X-Intranet': 'true'},
                    timeout=15
                )

                if resp.status_code != 200:
                    marcar_enlace(False)
                    return

                marcar_enlace(True)
                data = resp.json()
                nuevos_pats = data.get('pacientes', [])
                nuevas_cons = data.get('consultas', [])

                # Importar pacientes nuevos de otras instalaciones
                for p_data in nuevos_pats:
                    existente = Paciente.query.filter_by(uuid=p_data.get('uuid')).first()
                    if not existente:
                        self._importar_paciente(p_data)

                # Importar consultas nuevas de otras instalaciones
                for c_data in nuevas_cons:
                    existente = Consulta.query.filter_by(uuid=c_data.get('uuid')).first()
                    if not existente:
                        self._importar_consulta(c_data)

                if nuevos_pats or nuevas_cons:
                    db.session.commit()
                    log.info(f"Pull: {len(nuevos_pats)} pacientes, "
                             f"{len(nuevas_cons)} consultas de otras instalaciones")

                self._guardar_ultimo_pull(datetime.utcnow().isoformat())

            except requests.exceptions.ConnectionError:
                marcar_enlace(False)
            except Exception as e:
                log.error(f"Intranet pull error: {e}")

    def _importar_paciente(self, data: dict):
        """Crea localmente un paciente que llegó del central."""
        from app.models.models import db, Paciente, Distrito, Barrio
        from datetime import date
        try:
            fecha_nac = datetime.strptime(data['fecha_nacimiento'], '%Y-%m-%d').date()
            p = Paciente(
                uuid=data['uuid'],
                numero_historia=data.get('numero_historia', data['uuid'][:12]),
                dni=data.get('dni'),
                nombres=data['nombres'],
                apellidos=data['apellidos'],
                fecha_nacimiento=fecha_nac,
                sexo=data['sexo'],
                telefono=data.get('telefono'),
                direccion=data.get('direccion'),
                etnia=data.get('etnia'),
                ocupacion=data.get('ocupacion'),
                grupo_sanguineo=data.get('grupo_sanguineo'),
                alergias=data.get('alergias'),
                condiciones_cronicas=data.get('condiciones_cronicas'),
                sincronizado=True,
            )
            db.session.add(p)
        except Exception as e:
            log.warning(f"No se pudo importar paciente {data.get('uuid')}: {e}")

    def _importar_consulta(self, data: dict):
        """Crea localmente una consulta que llegó del central."""
        from app.models.models import db, Consulta, Paciente, Enfermedad, Diagnostico, Prescripcion
        try:
            paciente = Paciente.query.filter_by(uuid=data.get('paciente_uuid')).first()
            if not paciente:
                return  # El paciente aún no ha llegado — se intentará en el próximo pull

            fecha = datetime.fromisoformat(data['fecha_consulta'])
            c = Consulta(
                uuid=data['uuid'],
                paciente_id=paciente.id,
                medico_id=1,              # Usuario sistema para datos externos
                instalacion_id=None,
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
            db.session.add(c)
            db.session.flush()

            for d in data.get('diagnosticos', []):
                enf = Enfermedad.query.filter_by(codigo_icd10=d['codigo_icd10']).first()
                if enf:
                    db.session.add(Diagnostico(
                        consulta_id=c.id, enfermedad_id=enf.id,
                        tipo=d.get('tipo', 'definitivo')
                    ))
        except Exception as e:
            log.warning(f"No se pudo importar consulta {data.get('uuid')}: {e}")

    # ── Pendientes en BD ─────────────────────────────────────────────────────

    def _reencolar_pendientes_bd(self):
        """
        Al reiniciar el proceso, los registros pendientes en la BD
        que no están en la cola en memoria se vuelven a encolar.
        """
        with self.app.app_context():
            from app.models.models import RegistroSync
            pendientes = RegistroSync.query.filter_by(estado='pendiente').limit(100).all()
            reencolados = 0
            for r in pendientes:
                _write_queue.put({'tipo': r.tipo_dato, 'uuid': r.uuid_registro,
                                  'ts': r.timestamp.isoformat()})
                reencolados += 1
            if reencolados:
                log.info(f"Reencolados {reencolados} registros pendientes de la BD")

    # ── Persistencia del timestamp de pull ───────────────────────────────────

    def _leer_ultimo_pull(self) -> str:
        """Lee el timestamp del último pull exitoso."""
        try:
            import os
            path = os.path.join(self.app.root_path, '..', 'logs', 'ultimo_pull.txt')
            with open(path, 'r') as f:
                return f.read().strip()
        except Exception:
            return '2020-01-01T00:00:00'   # Primera vez: descargar todo

    def _guardar_ultimo_pull(self, ts: str):
        try:
            import os
            log_dir = os.path.join(self.app.root_path, '..', 'logs')
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, 'ultimo_pull.txt'), 'w') as f:
                f.write(ts)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# INSTANCIA GLOBAL
# ─────────────────────────────────────────────────────────────────────────────
intranet_engine: IntranetSyncEngine = None


def init_intranet(app) -> IntranetSyncEngine:
    global intranet_engine
    intranet_engine = IntranetSyncEngine(app)
    if app.config.get('INTRANET_MODE'):
        intranet_engine.iniciar()
        log.info("Motor de intranet sync iniciado.")
    return intranet_engine
