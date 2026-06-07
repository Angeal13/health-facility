"""
Generación de PDFs para Bioko Health usando ReportLab.
Historia Clínica y Reportes Epidemiológicos.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                  TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from datetime import datetime, timedelta


# Colores institucionales Bioko Health
COLOR_PRIMARIO = colors.HexColor('#1a6b4a')
COLOR_SECUNDARIO = colors.HexColor('#2d9c6e')
COLOR_GRIS = colors.HexColor('#f5f5f5')
COLOR_TEXTO = colors.HexColor('#2c2c2c')
COLOR_ALERTA = colors.HexColor('#c0392b')


def _estilos():
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(
        name='Titulo',
        fontSize=16, textColor=COLOR_PRIMARIO,
        spaceAfter=6, alignment=TA_CENTER, fontName='Helvetica-Bold'
    ))
    estilos.add(ParagraphStyle(
        name='Subtitulo',
        fontSize=11, textColor=COLOR_SECUNDARIO,
        spaceAfter=4, fontName='Helvetica-Bold'
    ))
    estilos.add(ParagraphStyle(
        name='Campo',
        fontSize=9, textColor=COLOR_TEXTO,
        spaceAfter=2, fontName='Helvetica'
    ))
    estilos.add(ParagraphStyle(
        name='CampoNegrita',
        fontSize=9, textColor=COLOR_TEXTO,
        spaceAfter=2, fontName='Helvetica-Bold'
    ))
    estilos.add(ParagraphStyle(
        name='Alerta',
        fontSize=9, textColor=COLOR_ALERTA,
        spaceAfter=2, fontName='Helvetica-Bold'
    ))
    return estilos


def _encabezado(story, titulo, subtitulo=None):
    estilos = _estilos()
    story.append(Paragraph('🏥 BIOKO HEALTH — Sistema de Salud', estilos['Titulo']))
    story.append(Paragraph('República de Guinea Ecuatorial', estilos['Campo']))
    story.append(HRFlowable(width='100%', thickness=2, color=COLOR_PRIMARIO))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(titulo, estilos['Subtitulo']))
    if subtitulo:
        story.append(Paragraph(subtitulo, estilos['Campo']))
    story.append(Spacer(1, 0.3 * cm))


def _tabla_datos(datos, col_widths=None):
    """Genera una tabla de dos columnas: etiqueta / valor."""
    style = TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), COLOR_GRIS),
        ('TEXTCOLOR', (0, 0), (0, -1), COLOR_PRIMARIO),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, COLOR_GRIS]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ])
    if not col_widths:
        col_widths = [5 * cm, 12 * cm]
    return Table(datos, colWidths=col_widths, style=style)


def generar_historia_pdf(paciente) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm
    )
    story = []
    estilos = _estilos()

    _encabezado(story, 'HISTORIA CLÍNICA',
                f'Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}')

    # Datos del paciente
    story.append(Paragraph('IDENTIFICACIÓN DEL PACIENTE', estilos['Subtitulo']))
    datos_paciente = [
        ['N° Historia', paciente.numero_historia],
        ['Nombres y Apellidos', paciente.nombre_completo],
        ['Fecha de Nacimiento', paciente.fecha_nacimiento.strftime('%d/%m/%Y') if paciente.fecha_nacimiento else '-'],
        ['Edad', f'{paciente.edad} años'],
        ['Sexo', 'Masculino' if paciente.sexo == 'M' else 'Femenino'],
        ['DNI / Cédula', paciente.dni or 'No registrado'],
        ['Teléfono', paciente.telefono or 'No registrado'],
        ['Distrito', paciente.distrito.nombre if paciente.distrito else '-'],
        ['Barrio', paciente.barrio.nombre if paciente.barrio else '-'],
        ['Dirección', paciente.direccion or '-'],
        ['Grupo Sanguíneo', paciente.grupo_sanguineo or 'No registrado'],
        ['Alergias', paciente.alergias or 'Ninguna conocida'],
        ['Cond. Crónicas', paciente.condiciones_cronicas or 'Ninguna registrada'],
    ]
    story.append(_tabla_datos(datos_paciente))
    story.append(Spacer(1, 0.5 * cm))

    # Historial de consultas
    consultas = paciente.consultas.order_by('fecha_consulta').all()
    story.append(Paragraph(f'HISTORIAL DE CONSULTAS ({len(consultas)} registros)', estilos['Subtitulo']))

    for consulta in consultas:
        story.append(Spacer(1, 0.2 * cm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=COLOR_SECUNDARIO))

        fecha_str = consulta.fecha_consulta.strftime('%d/%m/%Y %H:%M')
        medico = consulta.medico.nombre_completo if consulta.medico else '-'
        instalacion = consulta.instalacion.nombre if consulta.instalacion else '-'

        story.append(Paragraph(
            f'<b>{fecha_str}</b> — {consulta.tipo.replace("_", " ").title()} | '
            f'{instalacion} | Dr/a. {medico}',
            estilos['Campo']
        ))

        # Signos vitales
        vitales = []
        if consulta.temperatura:
            vitales.append(f'T°: {consulta.temperatura}°C')
        if consulta.presion_sistolica:
            vitales.append(f'PA: {consulta.presion_sistolica}/{consulta.presion_diastolica} mmHg')
        if consulta.frecuencia_cardiaca:
            vitales.append(f'FC: {consulta.frecuencia_cardiaca} lpm')
        if consulta.saturacion_oxigeno:
            vitales.append(f'SpO2: {consulta.saturacion_oxigeno}%')
        if consulta.peso_kg:
            vitales.append(f'Peso: {consulta.peso_kg} kg')

        if vitales:
            story.append(Paragraph('Signos vitales: ' + ' | '.join(vitales), estilos['Campo']))

        story.append(Paragraph(f'<b>Motivo:</b> {consulta.motivo_consulta}', estilos['Campo']))

        # Diagnósticos
        diags = consulta.diagnosticos.all()
        if diags:
            diag_str = ', '.join([
                f'{d.enfermedad.codigo_icd10} {d.enfermedad.nombre_es} ({d.tipo})'
                for d in diags
            ])
            story.append(Paragraph(f'<b>Diagnósticos:</b> {diag_str}', estilos['Campo']))

        # Prescripciones
        rxs = consulta.medicamentos.all()
        if rxs:
            rx_str = ' | '.join([f'{r.medicamento} {r.dosis or ""} {r.frecuencia or ""}' for r in rxs])
            story.append(Paragraph(f'<b>Tratamiento:</b> {rx_str}', estilos['Campo']))

        if consulta.plan_tratamiento:
            story.append(Paragraph(f'<b>Plan:</b> {consulta.plan_tratamiento}', estilos['Campo']))

    # Vacunas
    vacunas = paciente.vacunas.all()
    if vacunas:
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph('VACUNACIÓN', estilos['Subtitulo']))
        vac_data = [['Vacuna', 'Fecha', 'Dosis', 'Lote']]
        for v in vacunas:
            vac_data.append([
                v.nombre_vacuna,
                v.fecha_aplicacion.strftime('%d/%m/%Y'),
                str(v.dosis_numero),
                v.lote or '-'
            ])
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARIO),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_GRIS]),
        ])
        story.append(Table(vac_data,
                           colWidths=[8 * cm, 3 * cm, 2 * cm, 4 * cm],
                           style=style))

    # Pie de página
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width='100%', thickness=1, color=COLOR_PRIMARIO))
    story.append(Paragraph(
        f'Documento generado por BIOKO HEALTH el {datetime.now().strftime("%d/%m/%Y a las %H:%M")}. '
        'Uso exclusivo del personal sanitario autorizado.',
        estilos['Campo']
    ))

    doc.build(story)
    return buffer.getvalue()


def generar_reporte_epidemiologico_pdf(dias=30) -> bytes:
    from app.models.models import db, Diagnostico, Consulta, Paciente, Distrito, Enfermedad
    from sqlalchemy import func

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    story = []
    estilos = _estilos()
    fecha_inicio = datetime.utcnow() - timedelta(days=dias)

    _encabezado(story, 'REPORTE EPIDEMIOLÓGICO',
                f'Período: últimos {dias} días — {datetime.now().strftime("%d/%m/%Y")}')

    # Top diagnósticos
    story.append(Paragraph('PRINCIPALES DIAGNÓSTICOS', estilos['Subtitulo']))
    datos = (
        db.session.query(
            Enfermedad.codigo_icd10,
            Enfermedad.nombre_es,
            func.count(Diagnostico.id).label('total')
        )
        .join(Diagnostico).join(Consulta)
        .filter(Consulta.fecha_consulta >= fecha_inicio)
        .group_by(Enfermedad.id)
        .order_by(func.count(Diagnostico.id).desc())
        .limit(15).all()
    )

    tabla_data = [['ICD-10', 'Diagnóstico', 'Casos']]
    for d in datos:
        tabla_data.append([d.codigo_icd10, d.nombre_es, str(d.total)])

    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARIO),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_GRIS]),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
    ])
    story.append(Table(tabla_data, colWidths=[2.5 * cm, 12 * cm, 2.5 * cm], style=style))

    # Por distrito
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph('CASOS POR DISTRITO', estilos['Subtitulo']))
    por_distrito = (
        db.session.query(
            Distrito.nombre,
            func.count(Consulta.id).label('consultas'),
            func.count(func.distinct(Paciente.id)).label('pacientes')
        )
        .join(Paciente, Paciente.distrito_id == Distrito.id)
        .join(Consulta, Consulta.paciente_id == Paciente.id)
        .filter(Consulta.fecha_consulta >= fecha_inicio)
        .group_by(Distrito.id)
        .order_by(func.count(Consulta.id).desc())
        .all()
    )

    dist_data = [['Distrito', 'Consultas', 'Pacientes únicos']]
    for d in por_distrito:
        dist_data.append([d.nombre, str(d.consultas), str(d.pacientes)])

    story.append(Table(dist_data, colWidths=[9 * cm, 3.5 * cm, 4.5 * cm], style=style))

    doc.build(story)
    return buffer.getvalue()
