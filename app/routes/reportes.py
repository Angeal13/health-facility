from flask import Blueprint, render_template, Response, request, abort
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from io import BytesIO

from app.models.models import (db, Paciente, Consulta, Diagnostico, Enfermedad,
                                Distrito, AlertaEpidemiologica)
from app.utils.pdf_generator import generar_historia_pdf, generar_reporte_epidemiologico_pdf

reportes_bp = Blueprint('reportes', __name__)


@reportes_bp.route('/historia/<int:paciente_id>')
@login_required
def historia_clinica(paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    pdf_bytes = generar_historia_pdf(paciente)

    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'inline; filename=HC_{paciente.numero_historia}.pdf'
        }
    )


@reportes_bp.route('/epidemiologico')
@login_required
def epidemiologico():
    if not current_user.puede_ver_epidemiologia:
        abort(403)

    dias = request.args.get('dias', 30, type=int)
    pdf_bytes = generar_reporte_epidemiologico_pdf(dias)

    fecha_str = datetime.now().strftime('%Y%m%d')
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename=Reporte_Epidemiologico_{fecha_str}.pdf'
        }
    )


@reportes_bp.route('/exportar-csv')
@login_required
def exportar_csv():
    """Exportación CSV compatible con WHO/DHIS2."""
    if not current_user.es_admin:
        abort(403)

    import csv
    from io import StringIO
    from sqlalchemy import func

    dias = request.args.get('dias', 30, type=int)
    fecha_inicio = datetime.utcnow() - timedelta(days=dias)

    datos = (
        db.session.query(
            Distrito.nombre.label('distrito'),
            Enfermedad.codigo_icd10,
            Enfermedad.nombre_es,
            func.count(Diagnostico.id).label('casos')
        )
        .join(Paciente, Paciente.distrito_id == Distrito.id)
        .join(Consulta, Consulta.paciente_id == Paciente.id)
        .join(Diagnostico, Diagnostico.consulta_id == Consulta.id)
        .join(Enfermedad, Diagnostico.enfermedad_id == Enfermedad.id)
        .filter(Consulta.fecha_consulta >= fecha_inicio)
        .group_by(Distrito.id, Enfermedad.id)
        .order_by(Distrito.nombre, func.count(Diagnostico.id).desc())
        .all()
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Distrito', 'Código ICD-10', 'Diagnóstico', 'Casos', 'Periodo (días)'])
    for d in datos:
        writer.writerow([d.distrito, d.codigo_icd10, d.nombre_es, d.casos, dias])

    fecha_str = datetime.now().strftime('%Y%m%d')
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=Datos_Epidemiologicos_{fecha_str}.csv'}
    )
