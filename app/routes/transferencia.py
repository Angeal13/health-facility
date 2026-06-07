"""
Rutas de transferencia entre instalaciones y panel de estado de sincronización.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from app.models.models import db, Paciente, Instalacion, RegistroSync

transferencia_bp = Blueprint('transferencia', __name__)


# ─────────────────────────────────────────────
# TRANSFERENCIA INMEDIATA DE PACIENTE
# ─────────────────────────────────────────────

@transferencia_bp.route('/paciente/<int:paciente_id>', methods=['GET', 'POST'])
@login_required
def transferir_paciente(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    instalaciones = Instalacion.query.filter_by(activa=True).all()

    if request.method == 'POST':
        from app.utils.sync_scheduler import sync_manager

        if not sync_manager:
            flash('Servicio de sincronización no disponible.', 'danger')
            return redirect(url_for('pacientes.ver', id=paciente_id))

        resultado = sync_manager.transferir_paciente_ahora(
            paciente_id=paciente_id,
            instalacion_destino_id=request.form.get('instalacion_destino', type=int)
        )

        # Guardar nota de transferencia
        motivo = request.form.get('motivo', '').strip()
        _registrar_evento_transferencia(paciente_id, resultado, motivo)

        if resultado['ok']:
            flash(
                f"✓ Transferencia exitosa: {resultado['mensaje']}",
                'success'
            )
        else:
            flash(
                f"⚠ Transferencia parcial: {resultado['mensaje']}",
                'warning'
            )
            for err in resultado.get('errores', []):
                flash(f"Error: {err}", 'danger')

        return redirect(url_for('pacientes.ver', id=paciente_id))

    return render_template('transferencia/transferir.html',
                           paciente=paciente,
                           instalaciones=instalaciones)


@transferencia_bp.route('/paciente/<int:paciente_id>/estado-ajax')
@login_required
def estado_transferencia_ajax(paciente_id):
    """Estado de sync de un paciente específico (para polling en UI)."""
    paciente = Paciente.query.get_or_404(paciente_id)
    consultas = paciente.consultas.all()

    pendientes = sum(1 for c in consultas if not c.sincronizado)
    total = len(consultas)

    return jsonify({
        'paciente_sincronizado': paciente.sincronizado,
        'consultas_total': total,
        'consultas_pendientes': pendientes,
        'consultas_sincronizadas': total - pendientes,
    })


# ─────────────────────────────────────────────
# PANEL DE ESTADO DE SINCRONIZACIÓN
# ─────────────────────────────────────────────

@transferencia_bp.route('/estado')
@login_required
def estado_sync():
    if not current_user.es_admin:
        from flask import abort
        abort(403)

    from app.utils.sync_scheduler import sync_manager
    from flask import current_app

    estado = None
    if sync_manager:
        estado = sync_manager.estado_sync()

    # Últimos 50 registros de sync
    ultimos = RegistroSync.query.order_by(
        RegistroSync.timestamp.desc()
    ).limit(50).all()

    # Estadísticas
    from sqlalchemy import func
    stats_estado = db.session.query(
        RegistroSync.estado,
        func.count(RegistroSync.id)
    ).group_by(RegistroSync.estado).all()

    stats_tipo = db.session.query(
        RegistroSync.tipo_dato,
        func.count(RegistroSync.id)
    ).group_by(RegistroSync.tipo_dato).all()

    return render_template('transferencia/estado_sync.html',
                           estado=estado,
                           ultimos=ultimos,
                           stats_estado=dict(stats_estado),
                           stats_tipo=dict(stats_tipo),
                           sync_habilitado=current_app.config.get('SYNC_ENABLED', False),
                           servidor_central=current_app.config.get('CENTRAL_SERVER_URL', ''))


@transferencia_bp.route('/forzar-sync', methods=['POST'])
@login_required
def forzar_sync():
    """Ejecuta el sync completo inmediatamente (sin esperar las 02:00)."""
    if not current_user.es_admin:
        from flask import abort
        abort(403)

    from app.utils.sync_scheduler import sync_manager
    if not sync_manager:
        return jsonify({'ok': False, 'error': 'Sync manager no disponible'})

    import threading
    hilo = threading.Thread(
        target=sync_manager._ejecutar_sync_completo,
        daemon=True
    )
    hilo.start()

    return jsonify({
        'ok': True,
        'mensaje': 'Sincronización iniciada en segundo plano.',
        'timestamp': datetime.utcnow().isoformat()
    })


@transferencia_bp.route('/resolver-conflicto/<int:sync_id>', methods=['POST'])
@login_required
def resolver_conflicto(sync_id):
    """Marca un conflicto de DNI como resuelto manualmente."""
    if not current_user.es_admin:
        from flask import abort
        abort(403)

    registro = RegistroSync.query.get_or_404(sync_id)
    accion = request.form.get('accion', 'omitir')  # omitir | reintentar

    if accion == 'reintentar':
        registro.estado = 'pendiente'
        registro.error_mensaje = None
        flash('Registro marcado para reintento.', 'info')
    else:
        registro.estado = 'omitido'
        flash('Conflicto marcado como resuelto (omitido).', 'success')

    db.session.commit()
    return redirect(url_for('transferencia.estado_sync'))


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _registrar_evento_transferencia(paciente_id, resultado, motivo):
    """Guarda un registro de auditoría de la transferencia."""
    import json
    try:
        nota = RegistroSync(
            instalacion_origen='MANUAL',
            tipo_dato='transferencia',
            uuid_registro=f'TRANSFER-{paciente_id}-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            accion='transferencia_manual',
            estado='enviado' if resultado['ok'] else 'error',
            error_mensaje=json.dumps({
                'motivo': motivo,
                'resultado': resultado.get('mensaje'),
                'errores': resultado.get('errores', [])
            })[:500]
        )
        db.session.add(nota)
        db.session.commit()
    except Exception:
        pass
