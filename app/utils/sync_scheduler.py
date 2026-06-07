"""
BIOKO HEALTH — Sincronización Automática
Programador APScheduler:
  - Sync completo cada 24 horas
  - Transferencia inmediata de paciente específico por solicitud
  - Reintentos automáticos con backoff exponencial
  - Registro detallado de cada operación
"""
import logging
import requests
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

log = logging.getLogger('bioko.sync')


# ─────────────────────────────────────────────
# FUNCIONES DE SERIALIZACIÓN
# ─────────────────────────────────────────────

def _serializar_paciente(paciente):
    return {
        'uuid': paciente.uuid,
        'numero_historia': paciente.numero_historia,
        'dni': paciente.dni,
        'nombres': paciente.nombres,
        'apellidos': paciente.apellidos,
        'fecha_nacimiento': paciente.fecha_nacimiento.isoformat(),
        'sexo': paciente.sexo,
        'telefono': paciente.telefono,
        'direccion': paciente.direccion,
        'etnia': paciente.etnia,
        'ocupacion': paciente.ocupacion,
        'grupo_sanguineo': paciente.grupo_sanguineo,
        'alergias': paciente.alergias,
        'condiciones_cronicas': paciente.condiciones_cronicas,
        'distrito_codigo': paciente.distrito.codigo if paciente.distrito else None,
        'barrio_nombre': paciente.barrio.nombre if paciente.barrio else None,
        'latitud': paciente.latitud,
        'longitud': paciente.longitud,
    }


def _serializar_consulta(consulta):
    return {
        'uuid': consulta.uuid,
        'paciente_uuid': consulta.paciente.uuid,
        'instalacion_codigo': consulta.instalacion.codigo if consulta.instalacion else None,
        'fecha_consulta': consulta.fecha_consulta.isoformat(),
        'tipo': consulta.tipo,
        'motivo_consulta': consulta.motivo_consulta,
        'historia_enfermedad': consulta.historia_enfermedad,
        'examen_fisico': consulta.examen_fisico,
        'plan_tratamiento': consulta.plan_tratamiento,
        'observaciones': consulta.observaciones,
        'temperatura': consulta.temperatura,
        'presion_sistolica': consulta.presion_sistolica,
        'presion_diastolica': consulta.presion_diastolica,
        'frecuencia_cardiaca': consulta.frecuencia_cardiaca,
        'frecuencia_respiratoria': consulta.frecuencia_respiratoria,
        'saturacion_oxigeno': consulta.saturacion_oxigeno,
        'peso_kg': consulta.peso_kg,
        'talla_cm': consulta.talla_cm,
        'diagnosticos': [
            {
                'codigo_icd10': d.enfermedad.codigo_icd10,
                'tipo': d.tipo,
                'es_principal': d.es_principal,
            }
            for d in consulta.diagnosticos.all()
        ],
        'prescripciones': [
            {
                'medicamento': r.medicamento,
                'dosis': r.dosis,
                'via': r.via,
                'frecuencia': r.frecuencia,
                'duracion_dias': r.duracion_dias,
            }
            for r in consulta.medicamentos.all()
        ],
    }


# ─────────────────────────────────────────────
# CLASE PRINCIPAL DE SINCRONIZACIÓN
# ─────────────────────────────────────────────

class SyncManager:
    def __init__(self, app):
        self.app = app
        self.scheduler = BackgroundScheduler(
            timezone='Africa/Malabo',
            job_defaults={
                'coalesce': True,        # Si se perdieron ejecuciones, ejecutar sólo una
                'max_instances': 1,      # No ejecutar en paralelo
                'misfire_grace_time': 600  # 10 min de gracia si el servidor estuvo caído
            }
        )
        self.scheduler.add_listener(self._on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    def iniciar(self):
        """Inicia el scheduler con todos los jobs programados."""
        # Sync automático cada 24 horas a las 02:00
        self.scheduler.add_job(
            func=self._ejecutar_sync_completo,
            trigger=CronTrigger(hour=2, minute=0),
            id='sync_diario',
            name='Sincronización Diaria con Servidor Central',
            replace_existing=True
        )

        # Reintento de registros fallidos cada 6 horas
        self.scheduler.add_job(
            func=self._reintentar_fallidos,
            trigger=IntervalTrigger(hours=6),
            id='reintentos_sync',
            name='Reintento Registros Fallidos',
            replace_existing=True
        )

        self.scheduler.start()
        log.info("✓ Scheduler de sincronización iniciado. Próximo sync: 02:00 hora local.")

    def detener(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def _on_job_event(self, event):
        if event.exception:
            log.error(f"Job '{event.job_id}' falló: {event.exception}")
        else:
            log.info(f"Job '{event.job_id}' completado correctamente.")

    # ─────────────────────────────────────────
    # SYNC COMPLETO (24h)
    # ─────────────────────────────────────────

    def _ejecutar_sync_completo(self):
        """Envía todos los registros pendientes al servidor central."""
        with self.app.app_context():
            from app.models.models import db, RegistroSync, Paciente, Consulta
            from flask import current_app

            cfg = current_app.config
            if not cfg.get('SYNC_ENABLED') or not cfg.get('CENTRAL_SERVER_URL'):
                log.info("Sync deshabilitado o sin servidor central configurado.")
                return

            pendientes = RegistroSync.query.filter_by(estado='pendiente').all()
            if not pendientes:
                log.info("Sync: Sin registros pendientes.")
                self._registrar_sync_log('sync_completo', 0, 0, 0)
                return

            log.info(f"Sync: Iniciando envío de {len(pendientes)} registros pendientes.")
            enviados = errores = omitidos = 0

            for registro in pendientes:
                exito = self._enviar_registro(registro, cfg)
                if exito is True:
                    enviados += 1
                elif exito is False:
                    errores += 1
                else:
                    omitidos += 1

            db.session.commit()
            log.info(f"Sync completado: {enviados} enviados, {errores} errores, {omitidos} omitidos.")
            self._registrar_sync_log('sync_completo', enviados, errores, omitidos)

    def _enviar_registro(self, registro, cfg, max_intentos=3):
        """
        Envía un registro individual al servidor central.
        Retorna True=enviado, False=error, None=omitido
        """
        from app.models.models import db, Paciente, Consulta

        url_base = cfg['CENTRAL_SERVER_URL'].rstrip('/')
        token = cfg.get('SYNC_API_TOKEN', '')
        headers = {
            'Content-Type': 'application/json',
            'X-Bioko-Token': token,
            'X-Instalacion': cfg.get('FACILITY_CODE', 'UNKNOWN'),
        }

        try:
            payload = None
            endpoint = None

            if registro.tipo_dato == 'paciente':
                paciente = Paciente.query.filter_by(uuid=registro.uuid_registro).first()
                if not paciente:
                    registro.estado = 'omitido'
                    return None
                payload = _serializar_paciente(paciente)
                endpoint = f'{url_base}/api/sync/recibir-paciente'

            elif registro.tipo_dato == 'consulta':
                consulta = Consulta.query.filter_by(uuid=registro.uuid_registro).first()
                if not consulta:
                    registro.estado = 'omitido'
                    return None
                payload = _serializar_consulta(consulta)
                endpoint = f'{url_base}/api/sync/recibir-consulta'
            else:
                registro.estado = 'omitido'
                return None

            resp = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=30
            )

            if resp.status_code in (200, 201):
                registro.estado = 'enviado'
                registro.intentos += 1
                return True
            elif resp.status_code == 409:
                # Conflicto de DNI: marcar para revisión manual
                registro.estado = 'conflicto'
                registro.error_mensaje = resp.json().get('error', 'conflicto')
                return None
            else:
                registro.intentos += 1
                registro.error_mensaje = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if registro.intentos >= max_intentos:
                    registro.estado = 'error'
                return False

        except requests.exceptions.ConnectionError:
            registro.intentos += 1
            registro.error_mensaje = "Sin conexión al servidor central"
            log.warning(f"Sync: Sin conexión al enviar {registro.uuid_registro}")
            return False
        except requests.exceptions.Timeout:
            registro.intentos += 1
            registro.error_mensaje = "Timeout de conexión"
            return False
        except Exception as e:
            registro.intentos += 1
            registro.error_mensaje = str(e)[:300]
            log.error(f"Sync error inesperado: {e}")
            return False

    # ─────────────────────────────────────────
    # REINTENTOS DE FALLIDOS
    # ─────────────────────────────────────────

    def _reintentar_fallidos(self):
        """Reintenta registros con error (hasta 3 intentos totales)."""
        with self.app.app_context():
            from app.models.models import db, RegistroSync
            from flask import current_app

            cfg = current_app.config
            if not cfg.get('SYNC_ENABLED') or not cfg.get('CENTRAL_SERVER_URL'):
                return

            fallidos = RegistroSync.query.filter(
                RegistroSync.estado == 'error',
                RegistroSync.intentos < 3
            ).limit(20).all()

            if not fallidos:
                return

            log.info(f"Reintentando {len(fallidos)} registros fallidos...")
            for registro in fallidos:
                registro.estado = 'pendiente'  # Resetear para reintento

            db.session.commit()

    # ─────────────────────────────────────────
    # TRANSFERENCIA INMEDIATA DE PACIENTE
    # ─────────────────────────────────────────

    def transferir_paciente_ahora(self, paciente_id, instalacion_destino_id=None):
        """
        Transfiere un paciente específico y todas sus consultas de forma inmediata.
        Llamada desde la ruta de transferencia.
        Retorna dict con resultado detallado.
        """
        with self.app.app_context():
            from app.models.models import db, Paciente, Consulta, RegistroSync
            from flask import current_app

            cfg = current_app.config
            resultado = {
                'ok': False,
                'paciente': None,
                'consultas_enviadas': 0,
                'errores': [],
                'mensaje': '',
                'timestamp': datetime.utcnow().isoformat()
            }

            if not cfg.get('SYNC_ENABLED') or not cfg.get('CENTRAL_SERVER_URL'):
                resultado['mensaje'] = 'Sync no habilitado. Configure SYNC_ENABLED y CENTRAL_SERVER_URL.'
                return resultado

            paciente = Paciente.query.get(paciente_id)
            if not paciente:
                resultado['mensaje'] = f'Paciente ID {paciente_id} no encontrado.'
                return resultado

            resultado['paciente'] = paciente.nombre_completo

            # 1. Enviar paciente
            reg_p = RegistroSync(
                instalacion_origen=cfg.get('FACILITY_CODE', 'LOCAL'),
                tipo_dato='paciente',
                uuid_registro=paciente.uuid,
                accion='crear',
                estado='pendiente'
            )
            db.session.add(reg_p)
            db.session.flush()

            exito_paciente = self._enviar_registro(reg_p, cfg)
            if exito_paciente is True:
                paciente.sincronizado = True
            elif exito_paciente is False:
                resultado['errores'].append(f"Error enviando datos del paciente: {reg_p.error_mensaje}")
                db.session.commit()
                resultado['mensaje'] = 'Falló la transferencia del paciente.'
                return resultado

            # 2. Enviar todas las consultas del paciente
            consultas = Consulta.query.filter_by(paciente_id=paciente_id).all()
            for consulta in consultas:
                reg_c = RegistroSync(
                    instalacion_origen=cfg.get('FACILITY_CODE', 'LOCAL'),
                    tipo_dato='consulta',
                    uuid_registro=consulta.uuid,
                    accion='crear',
                    estado='pendiente'
                )
                db.session.add(reg_c)
                db.session.flush()

                exito = self._enviar_registro(reg_c, cfg)
                if exito is True:
                    consulta.sincronizado = True
                    resultado['consultas_enviadas'] += 1
                elif exito is False:
                    resultado['errores'].append(
                        f"Consulta {consulta.uuid[:8]}... — {reg_c.error_mensaje}"
                    )

            db.session.commit()

            total = len(consultas)
            enviadas = resultado['consultas_enviadas']
            resultado['ok'] = len(resultado['errores']) == 0
            resultado['mensaje'] = (
                f"Transferencia completada: {enviadas}/{total} consultas enviadas."
                if resultado['ok'] else
                f"Transferencia parcial: {enviadas}/{total} consultas. Ver errores."
            )
            return resultado

    # ─────────────────────────────────────────
    # LOG INTERNO DE SINCRONIZACIONES
    # ─────────────────────────────────────────

    def _registrar_sync_log(self, tipo, enviados, errores, omitidos):
        try:
            import os
            log_path = os.path.join(self.app.root_path, '..', 'logs', 'sync.log')
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(
                    f"{datetime.utcnow().isoformat()} | {tipo} | "
                    f"enviados={enviados} errores={errores} omitidos={omitidos}\n"
                )
        except Exception:
            pass

    def estado_sync(self):
        """Retorna estado actual del scheduler y estadísticas de sync."""
        with self.app.app_context():
            from app.models.models import RegistroSync
            stats = {}
            for estado in ('pendiente', 'enviado', 'error', 'conflicto', 'omitido'):
                stats[estado] = RegistroSync.query.filter_by(estado=estado).count()

            jobs = []
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time
                jobs.append({
                    'id': job.id,
                    'nombre': job.name,
                    'proxima_ejecucion': next_run.isoformat() if next_run else None,
                })

            return {
                'activo': self.scheduler.running,
                'jobs': jobs,
                'registros': stats
            }


# ─────────────────────────────────────────────
# INSTANCIA GLOBAL (inicializada en __init__.py)
# ─────────────────────────────────────────────
sync_manager: SyncManager = None


def init_sync(app):
    global sync_manager
    sync_manager = SyncManager(app)
    if app.config.get('SYNC_ENABLED'):
        sync_manager.iniciar()
    return sync_manager
