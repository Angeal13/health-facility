"""
BIOKO HEALTH — Modelos de Base de Datos
Cubre: Pacientes, Encuentros, Síntomas, Diagnósticos, Ubicaciones, Usuarios
Diseñado para escalar a Río Muni.
"""
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt
import uuid

db = SQLAlchemy()
bcrypt = Bcrypt()


def gen_uuid():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
# GEOGRAFÍA
# ─────────────────────────────────────────────

class Region(db.Model):
    """Bioko Norte, Bioko Sur, Centro Sur, Kié-Ntem, etc."""
    __tablename__ = 'regiones'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    isla = db.Column(db.Boolean, default=True)  # True=Bioko, False=Río Muni
    activa = db.Column(db.Boolean, default=True)

    distritos = db.relationship('Distrito', backref='region', lazy='dynamic')


class Distrito(db.Model):
    __tablename__ = 'distritos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('regiones.id'), nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)

    barrios = db.relationship('Barrio', backref='distrito', lazy='dynamic')
    pacientes = db.relationship('Paciente', backref='distrito', lazy='dynamic')


class Barrio(db.Model):
    __tablename__ = 'barrios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    distrito_id = db.Column(db.Integer, db.ForeignKey('distritos.id'), nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    poblacion_estimada = db.Column(db.Integer)

    pacientes = db.relationship('Paciente', backref='barrio', lazy='dynamic')


# ─────────────────────────────────────────────
# INSTALACIONES SANITARIAS
# ─────────────────────────────────────────────

class Instalacion(db.Model):
    __tablename__ = 'instalaciones'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), unique=True, nullable=False)
    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)  # hospital, clinica, puesto, laboratorio
    distrito_id = db.Column(db.Integer, db.ForeignKey('distritos.id'))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    telefono = db.Column(db.String(30))
    activa = db.Column(db.Boolean, default=True)
    es_nodo_local = db.Column(db.Boolean, default=False)  # Esta instalación es el servidor local
    provincia_id = db.Column(db.Integer, db.ForeignKey('provincias.id'), nullable=True)

    usuarios = db.relationship('Usuario', backref='instalacion', lazy='dynamic')
    consultas = db.relationship('Consulta', backref='instalacion', lazy='dynamic',
                                foreign_keys='Consulta.instalacion_id')


# ─────────────────────────────────────────────
# USUARIOS Y ROLES
# ─────────────────────────────────────────────

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=gen_uuid)
    nombre_usuario = db.Column(db.String(80), unique=True, nullable=False)
    nombre_completo = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120))
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(30), nullable=False)
    # Roles: superadmin | admin | medico | enfermero | laboratorio | epidemiologia | recepcion
    instalacion_id = db.Column(db.Integer, db.ForeignKey('instalaciones.id'))
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acceso = db.Column(db.DateTime)

    consultas = db.relationship('Consulta', backref='medico', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def es_medico(self):
        return self.rol in ('medico', 'superadmin', 'admin')

    @property
    def es_admin(self):
        return self.rol in ('superadmin', 'admin')

    @property
    def puede_ver_epidemiologia(self):
        return self.rol in ('superadmin', 'admin', 'epidemiologia', 'medico')


# ─────────────────────────────────────────────
# PACIENTES
# ─────────────────────────────────────────────

class Paciente(db.Model):
    __tablename__ = 'pacientes'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=gen_uuid)
    # Identificación
    numero_historia = db.Column(db.String(20), unique=True, nullable=False)
    dni = db.Column(db.String(30), unique=True)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    sexo = db.Column(db.String(1), nullable=False)  # M / F
    # Contacto
    telefono = db.Column(db.String(30))
    # Ubicación
    barrio_id = db.Column(db.Integer, db.ForeignKey('barrios.id'))
    distrito_id = db.Column(db.Integer, db.ForeignKey('distritos.id'))
    direccion = db.Column(db.String(255))
    latitud = db.Column(db.Float)   # GPS del domicilio si disponible
    longitud = db.Column(db.Float)
    # Demografía
    etnia = db.Column(db.String(50))
    ocupacion = db.Column(db.String(100))
    nivel_educativo = db.Column(db.String(50))
    # Clínico
    grupo_sanguineo = db.Column(db.String(5))
    alergias = db.Column(db.Text)
    condiciones_cronicas = db.Column(db.Text)
    # Metadata
    foto = db.Column(db.String(255))
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    instalacion_origen_id = db.Column(db.Integer, db.ForeignKey('instalaciones.id'))
    sincronizado = db.Column(db.Boolean, default=False)
    hash_integridad = db.Column(db.String(64))  # Para verificar datos en sync

    consultas = db.relationship('Consulta', backref='paciente', lazy='dynamic',
                                 order_by='Consulta.fecha_consulta.desc()')
    vacunas = db.relationship('Vacuna', backref='paciente', lazy='dynamic')

    @property
    def edad(self):
        today = date.today()
        born = self.fecha_nacimiento
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    def __repr__(self):
        return f'<Paciente {self.numero_historia}: {self.nombre_completo}>'


# ─────────────────────────────────────────────
# CATÁLOGO ICD-10 (ENFERMEDADES)
# ─────────────────────────────────────────────

class Enfermedad(db.Model):
    __tablename__ = 'enfermedades'
    id = db.Column(db.Integer, primary_key=True)
    codigo_icd10 = db.Column(db.String(10), unique=True, nullable=False)
    nombre_es = db.Column(db.String(255), nullable=False)
    nombre_en = db.Column(db.String(255))
    categoria = db.Column(db.String(100))
    subcategoria = db.Column(db.String(100))
    es_notificable = db.Column(db.Boolean, default=False)  # Notificación obligatoria al Ministerio
    es_tropical = db.Column(db.Boolean, default=False)     # Enfermedades tropicales prioritarias
    activa = db.Column(db.Boolean, default=True)

    diagnosticos = db.relationship('Diagnostico', backref='enfermedad', lazy='dynamic')


class Sintoma(db.Model):
    __tablename__ = 'sintomas'
    id = db.Column(db.Integer, primary_key=True)
    nombre_es = db.Column(db.String(150), nullable=False, unique=True)
    nombre_en = db.Column(db.String(150))
    categoria = db.Column(db.String(80))  # respiratorio, gastrointestinal, neurológico, etc.
    activo = db.Column(db.Boolean, default=True)


# ─────────────────────────────────────────────
# CONSULTAS (ENCUENTROS MÉDICOS)
# ─────────────────────────────────────────────

class Consulta(db.Model):
    __tablename__ = 'consultas'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=gen_uuid)
    paciente_id = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    medico_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    instalacion_id = db.Column(db.Integer, db.ForeignKey('instalaciones.id'), nullable=False)
    fecha_consulta = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    tipo = db.Column(db.String(30), nullable=False)
    # Tipos: primera_vez | seguimiento | urgencia | referido_entrante | referido_saliente | teleconsulta

    # Signos vitales
    temperatura = db.Column(db.Float)        # °C
    presion_sistolica = db.Column(db.Integer)
    presion_diastolica = db.Column(db.Integer)
    frecuencia_cardiaca = db.Column(db.Integer)
    frecuencia_respiratoria = db.Column(db.Integer)
    saturacion_oxigeno = db.Column(db.Float)
    peso_kg = db.Column(db.Float)
    talla_cm = db.Column(db.Float)

    # Clínico
    motivo_consulta = db.Column(db.Text, nullable=False)
    historia_enfermedad = db.Column(db.Text)
    examen_fisico = db.Column(db.Text)
    plan_tratamiento = db.Column(db.Text)
    observaciones = db.Column(db.Text)

    # Estado
    estado = db.Column(db.String(20), default='activa')  # activa | cerrada | referida
    referido_a_id = db.Column(db.Integer, db.ForeignKey('instalaciones.id'))

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    sincronizado = db.Column(db.Boolean, default=False)

    diagnosticos = db.relationship('Diagnostico', backref='consulta', lazy='dynamic',
                                    cascade='all, delete-orphan')
    sintomas_consulta = db.relationship('ConsultaSintoma', backref='consulta', lazy='dynamic',
                                         cascade='all, delete-orphan')
    medicamentos = db.relationship('Prescripcion', backref='consulta', lazy='dynamic',
                                    cascade='all, delete-orphan')
    examenes = db.relationship('ExamenLaboratorio', backref='consulta', lazy='dynamic',
                                cascade='all, delete-orphan')

    @property
    def imc(self):
        if self.peso_kg and self.talla_cm and self.talla_cm > 0:
            talla_m = self.talla_cm / 100
            return round(self.peso_kg / (talla_m ** 2), 1)
        return None


class ConsultaSintoma(db.Model):
    __tablename__ = 'consulta_sintomas'
    id = db.Column(db.Integer, primary_key=True)
    consulta_id = db.Column(db.Integer, db.ForeignKey('consultas.id'), nullable=False)
    sintoma_id = db.Column(db.Integer, db.ForeignKey('sintomas.id'), nullable=False)
    intensidad = db.Column(db.String(10))   # leve | moderado | severo
    duracion_dias = db.Column(db.Integer)
    notas = db.Column(db.String(255))
    sintoma = db.relationship('Sintoma')


class Diagnostico(db.Model):
    __tablename__ = 'diagnosticos'
    id = db.Column(db.Integer, primary_key=True)
    consulta_id = db.Column(db.Integer, db.ForeignKey('consultas.id'), nullable=False)
    enfermedad_id = db.Column(db.Integer, db.ForeignKey('enfermedades.id'), nullable=False)
    tipo = db.Column(db.String(20), default='definitivo')  # presuntivo | definitivo | descartado
    es_principal = db.Column(db.Boolean, default=True)
    notas = db.Column(db.Text)


class Prescripcion(db.Model):
    __tablename__ = 'prescripciones'
    id = db.Column(db.Integer, primary_key=True)
    consulta_id = db.Column(db.Integer, db.ForeignKey('consultas.id'), nullable=False)
    medicamento = db.Column(db.String(200), nullable=False)
    dosis = db.Column(db.String(100))
    via = db.Column(db.String(50))        # oral | IV | IM | tópico
    frecuencia = db.Column(db.String(100))
    duracion_dias = db.Column(db.Integer)
    instrucciones = db.Column(db.Text)


class ExamenLaboratorio(db.Model):
    __tablename__ = 'examenes_laboratorio'
    id = db.Column(db.Integer, primary_key=True)
    consulta_id = db.Column(db.Integer, db.ForeignKey('consultas.id'), nullable=False)
    nombre_examen = db.Column(db.String(200), nullable=False)
    fecha_solicitud = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_resultado = db.Column(db.DateTime)
    resultado = db.Column(db.Text)
    valores_referencia = db.Column(db.String(200))
    estado = db.Column(db.String(20), default='pendiente')  # pendiente | completado | cancelado
    notas = db.Column(db.Text)


# ─────────────────────────────────────────────
# VACUNAS
# ─────────────────────────────────────────────

class Vacuna(db.Model):
    __tablename__ = 'vacunas'
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    nombre_vacuna = db.Column(db.String(150), nullable=False)
    fecha_aplicacion = db.Column(db.Date, nullable=False)
    dosis_numero = db.Column(db.Integer, default=1)
    lote = db.Column(db.String(50))
    instalacion_id = db.Column(db.Integer, db.ForeignKey('instalaciones.id'))
    aplicado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    proxima_dosis = db.Column(db.Date)
    notas = db.Column(db.Text)


# ─────────────────────────────────────────────
# VIGILANCIA EPIDEMIOLÓGICA
# ─────────────────────────────────────────────

class AlertaEpidemiologica(db.Model):
    __tablename__ = 'alertas_epidemiologicas'
    id = db.Column(db.Integer, primary_key=True)
    enfermedad_id = db.Column(db.Integer, db.ForeignKey('enfermedades.id'), nullable=False)
    distrito_id = db.Column(db.Integer, db.ForeignKey('distritos.id'))
    barrio_id = db.Column(db.Integer, db.ForeignKey('barrios.id'))
    fecha_deteccion = db.Column(db.DateTime, default=datetime.utcnow)
    nivel = db.Column(db.String(20), nullable=False)  # vigilancia | alerta | emergencia
    casos_detectados = db.Column(db.Integer, nullable=False)
    periodo_dias = db.Column(db.Integer, default=7)
    descripcion = db.Column(db.Text)
    estado = db.Column(db.String(20), default='activa')  # activa | investigando | resuelta
    creado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    resuelta_en = db.Column(db.DateTime)

    enfermedad = db.relationship('Enfermedad')
    distrito = db.relationship('Distrito')


# ─────────────────────────────────────────────
# REGISTRO DE SINCRONIZACIÓN
# ─────────────────────────────────────────────

class RegistroSync(db.Model):
    __tablename__ = 'registros_sync'
    id = db.Column(db.Integer, primary_key=True)
    instalacion_origen = db.Column(db.String(30), nullable=False)
    tipo_dato = db.Column(db.String(30), nullable=False)  # paciente | consulta | alerta
    uuid_registro = db.Column(db.String(36), nullable=False)
    accion = db.Column(db.String(20), nullable=False)     # crear | actualizar | eliminar
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(20), default='pendiente')  # pendiente | enviado | error
    intentos = db.Column(db.Integer, default=0)
    error_mensaje = db.Column(db.Text)


# ─────────────────────────────────────────────
# REGISTRO DE NODOS DE RED
# ─────────────────────────────────────────────

class NodoInstalacion(db.Model):
    """
    Tabla que el servidor central mantiene con todos los nodos
    (instalaciones remotas) registrados en la red.
    Cada nodo es un servidor local dentro de una clínica u hospital.
    """
    __tablename__ = 'nodos_instalacion'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), unique=True, nullable=False)
    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(30))                  # hospital | clinica | puesto
    ip_lan = db.Column(db.String(45))                # IPv4/IPv6 dentro de su LAN
    puerto_lan = db.Column(db.Integer, default=5000)
    lan_url = db.Column(db.String(255))              # URL completa para acceder desde la LAN
    hostname = db.Column(db.String(100))
    estado = db.Column(db.String(20), default='activo')  # activo | inactivo | sin_conexion
    primer_contacto = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_contacto = db.Column(db.DateTime)
    version_app = db.Column(db.String(20))

    def __repr__(self):
        return f'<Nodo {self.codigo}: {self.nombre} @ {self.ip_lan}>'

    @property
    def minutos_desde_contacto(self):
        if not self.ultimo_contacto:
            return None
        delta = datetime.utcnow() - self.ultimo_contacto
        return int(delta.total_seconds() / 60)

    @property
    def en_linea(self):
        """Considera en línea si el último contacto fue hace menos de 30 min."""
        mins = self.minutos_desde_contacto
        return mins is not None and mins < 30


# ─────────────────────────────────────────────────────────────────────────────
# ARQUITECTURA NACIONAL DE 3 NIVELES
# ─────────────────────────────────────────────────────────────────────────────

class Provincia(db.Model):
    """
    Las 6 provincias / territorios de Guinea Ecuatorial.
    Cada una tiene exactamente un nodo provincial.
    """
    __tablename__ = 'provincias'
    id              = db.Column(db.Integer, primary_key=True)
    codigo          = db.Column(db.String(10), unique=True, nullable=False)
    nombre          = db.Column(db.String(100), nullable=False)
    sede            = db.Column(db.String(100))          # Ciudad capital de provincia
    isla            = db.Column(db.Boolean, default=False)
    # URL del nodo provincial de esta zona (vacío si este ES el nodo)
    nodo_url        = db.Column(db.String(255))
    nodo_codigo     = db.Column(db.String(20))
    activa          = db.Column(db.Boolean, default=True)

    instalaciones   = db.relationship('Instalacion', backref='provincia', lazy='dynamic',
                                       foreign_keys='Instalacion.provincia_id')





class SolicitudExpediente(db.Model):
    """
    Registro de cada solicitud de expediente entre nodos provinciales.

    Flujo:
      1. Instalación A (provincia X) solicita expediente de paciente P
      2. Nodo Provincial X crea esta solicitud y la enruta al Nodo Provincial Y
      3. Nodo Provincial Y responde con los datos del paciente
      4. Nodo Provincial X cachea el expediente (CacheExpediente)
      5. Instalación A lee el expediente desde su nodo provincial
    """
    __tablename__ = 'solicitudes_expediente'
    id                  = db.Column(db.Integer, primary_key=True)
    uuid                = db.Column(db.String(36), unique=True, default=gen_uuid)

    # Quién solicita
    instalacion_solicitante_codigo = db.Column(db.String(30), nullable=False)
    provincia_solicitante          = db.Column(db.String(10), nullable=False)

    # Quién tiene los datos
    provincia_origen               = db.Column(db.String(10), nullable=False)

    # El paciente
    paciente_uuid                  = db.Column(db.String(36), nullable=False)
    paciente_numero_historia       = db.Column(db.String(20))

    # Estado del flujo
    estado          = db.Column(db.String(20), default='pendiente')
    # pendiente → enviada → recibida → entregada → expirada
    motivo          = db.Column(db.Text)          # Motivo clínico de la solicitud
    urgente         = db.Column(db.Boolean, default=False)

    creada_en       = db.Column(db.DateTime, default=datetime.utcnow)
    respondida_en   = db.Column(db.DateTime)
    entregada_en    = db.Column(db.DateTime)
    expira_en       = db.Column(db.DateTime)      # Cuándo expira el caché local

    solicitada_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))


class CacheExpediente(db.Model):
    """
    Caché temporal de expedientes de pacientes de otras provincias.
    Se almacena en el nodo provincial solicitante por un período configurable.
    Solo lectura — las consultas nuevas se guardan localmente y se sincronizan
    de vuelta al nodo de origen vía el nodo provincial.
    """
    __tablename__ = 'cache_expedientes'
    id              = db.Column(db.Integer, primary_key=True)
    solicitud_id    = db.Column(db.Integer, db.ForeignKey('solicitudes_expediente.id'))

    paciente_uuid   = db.Column(db.String(36), nullable=False, index=True)
    provincia_origen = db.Column(db.String(10), nullable=False)
    instalacion_origen = db.Column(db.String(30))

    # El expediente completo serializado (JSON)
    datos_paciente  = db.Column(db.Text, nullable=False)   # JSON del paciente
    datos_consultas = db.Column(db.Text, nullable=False)   # JSON array de consultas
    datos_vacunas   = db.Column(db.Text)                   # JSON array de vacunas

    creado_en       = db.Column(db.DateTime, default=datetime.utcnow)
    expira_en       = db.Column(db.DateTime, nullable=False)
    activo          = db.Column(db.Boolean, default=True)

    solicitud       = db.relationship('SolicitudExpediente', backref='cache')

    @property
    def expirado(self):
        return datetime.utcnow() > self.expira_en


class TransferenciaPaciente(db.Model):
    """
    Transferencia formal de un paciente entre instalaciones.
    Diferente de SolicitudExpediente: aquí el paciente se MUEVE
    (cambia de instalación de atención primaria).
    El expediente completo se copia al nodo destino de forma permanente.
    """
    __tablename__ = 'transferencias_paciente'
    id              = db.Column(db.Integer, primary_key=True)
    uuid            = db.Column(db.String(36), unique=True, default=gen_uuid)

    paciente_id     = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    paciente_uuid   = db.Column(db.String(36), nullable=False)

    # Origen
    instalacion_origen_codigo  = db.Column(db.String(30), nullable=False)
    provincia_origen           = db.Column(db.String(10), nullable=False)

    # Destino
    instalacion_destino_codigo = db.Column(db.String(30), nullable=False)
    provincia_destino          = db.Column(db.String(10), nullable=False)

    motivo_clinico  = db.Column(db.Text, nullable=False)
    urgente         = db.Column(db.Boolean, default=False)
    estado          = db.Column(db.String(20), default='iniciada')
    # iniciada → en_transito → confirmada → completada → rechazada

    iniciada_en     = db.Column(db.DateTime, default=datetime.utcnow)
    confirmada_en   = db.Column(db.DateTime)
    completada_en   = db.Column(db.DateTime)
    notas           = db.Column(db.Text)

    iniciada_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    paciente        = db.relationship('Paciente', backref='transferencias')
