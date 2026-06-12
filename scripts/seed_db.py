"""
BIOKO HEALTH — Carga Inicial de Datos (Seed)
=============================================
Carga los catálogos base necesarios para operar:
    - Geografía: regiones, distritos, barrios
    - Provincias (arquitectura nacional de 3 niveles)
    - Enfermedades ICD-10 prioritarias (notificables y tropicales)
    - Síntomas comunes
    - Instalaciones sanitarias iniciales
    - Usuario administrador inicial + usuario sistema de sync

Uso:
    python scripts/seed_db.py            # Carga todo
    FLASK_ENV=production python scripts/seed_db.py
"""
import os
import sys
import secrets

# Permitir ejecutar desde la raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.models import (db, Region, Distrito, Barrio, Provincia,
                                Enfermedad, Sintoma, Instalacion, Usuario)


# ─────────────────────────────────────────────────────────────────────────────
# GEOGRAFÍA
# ─────────────────────────────────────────────────────────────────────────────

def seed_geografia():
    """Regiones y distritos de Guinea Ecuatorial."""
    if Region.query.first():
        print("  · Geografía ya cargada — omitiendo")
        return

    regiones = [
        # (nombre, codigo, isla)
        ('Bioko Norte', 'BN', True),
        ('Bioko Sur', 'BS', True),
        ('Annobón', 'AN', True),
        ('Litoral', 'LI', False),
        ('Centro Sur', 'CS', False),
        ('Kié-Ntem', 'KN', False),
        ('Wele-Nzas', 'WN', False),
    ]
    distritos = {
        'BN': [('Malabo', 'MAL', 3.7504, 8.7371), ('Baney', 'BAN', 3.6989, 8.9123),
               ('Rebola', 'REB', 3.7178, 8.8334)],
        'BS': [('Luba', 'LUB', 3.4568, 8.5547), ('Riaba', 'RIA', 3.3933, 8.7561)],
        'AN': [('San Antonio de Palé', 'PAL', -1.4068, 5.6322)],
        'LI': [('Bata', 'BAT', 1.8639, 9.7658), ('Mbini', 'MBI', 1.5833, 9.6167),
               ('Cogo', 'COG', 1.0833, 9.7000)],
        'CS': [('Evinayong', 'EVI', 1.4500, 10.5667), ('Niefang', 'NIE', 1.8439, 10.2356)],
        'KN': [('Ebebiyín', 'EBE', 2.1511, 11.3353), ('Micomeseng', 'MIC', 2.1333, 10.6167)],
        'WN': [('Mongomo', 'MON', 1.6287, 11.3168), ('Añisoc', 'ANI', 1.8500, 10.7667)],
    }

    for nombre, codigo, isla in regiones:
        r = Region(nombre=nombre, codigo=codigo, isla=isla)
        db.session.add(r)
        db.session.flush()
        for d_nombre, d_codigo, lat, lng in distritos.get(codigo, []):
            db.session.add(Distrito(nombre=d_nombre, codigo=d_codigo,
                                     region_id=r.id, latitud=lat, longitud=lng))
    db.session.commit()
    print(f"  ✓ {len(regiones)} regiones, "
          f"{sum(len(v) for v in distritos.values())} distritos")


def seed_provincias():
    """Las 6 provincias / territorios con sus sedes."""
    if Provincia.query.first():
        print("  · Provincias ya cargadas — omitiendo")
        return

    provincias = [
        # (codigo, nombre, sede, isla)
        ('BN', 'Bioko Norte', 'Malabo', True),
        ('BS', 'Bioko Sur', 'Luba', True),
        ('AN', 'Annobón', 'San Antonio de Palé', True),
        ('LI', 'Litoral', 'Bata', False),
        ('CS', 'Centro Sur', 'Evinayong', False),
        ('KN', 'Kié-Ntem', 'Ebebiyín', False),
        ('WN', 'Wele-Nzas', 'Mongomo', False),
    ]
    for codigo, nombre, sede, isla in provincias:
        db.session.add(Provincia(codigo=codigo, nombre=nombre, sede=sede, isla=isla))
    db.session.commit()
    print(f"  ✓ {len(provincias)} provincias")


# ─────────────────────────────────────────────────────────────────────────────
# ENFERMEDADES ICD-10
# ─────────────────────────────────────────────────────────────────────────────

def seed_enfermedades():
    """Catálogo inicial de enfermedades ICD-10 prioritarias para GQ."""
    if Enfermedad.query.first():
        print("  · Enfermedades ya cargadas — omitiendo")
        return

    enfermedades = [
        # (codigo, nombre_es, nombre_en, categoria, notificable, tropical)
        ('B50', 'Paludismo por Plasmodium falciparum', 'Falciparum malaria', 'Infecciosas', True, True),
        ('B51', 'Paludismo por Plasmodium vivax', 'Vivax malaria', 'Infecciosas', True, True),
        ('B54', 'Paludismo no especificado', 'Unspecified malaria', 'Infecciosas', True, True),
        ('A00', 'Cólera', 'Cholera', 'Infecciosas', True, True),
        ('A01', 'Fiebre tifoidea y paratifoidea', 'Typhoid fever', 'Infecciosas', True, True),
        ('A09', 'Diarrea y gastroenteritis infecciosa', 'Infectious gastroenteritis', 'Infecciosas', True, False),
        ('A15', 'Tuberculosis respiratoria', 'Respiratory tuberculosis', 'Infecciosas', True, False),
        ('A39', 'Meningitis meningocócica', 'Meningococcal meningitis', 'Infecciosas', True, False),
        ('A90', 'Dengue', 'Dengue fever', 'Infecciosas', True, True),
        ('A95', 'Fiebre amarilla', 'Yellow fever', 'Infecciosas', True, True),
        ('B20', 'Enfermedad por VIH', 'HIV disease', 'Infecciosas', True, False),
        ('B05', 'Sarampión', 'Measles', 'Infecciosas', True, False),
        ('B16', 'Hepatitis B aguda', 'Acute hepatitis B', 'Infecciosas', True, False),
        ('B76', 'Anquilostomiasis', 'Hookworm disease', 'Parasitarias', False, True),
        ('B65', 'Esquistosomiasis', 'Schistosomiasis', 'Parasitarias', True, True),
        ('J18', 'Neumonía no especificada', 'Pneumonia', 'Respiratorias', False, False),
        ('J06', 'Infección respiratoria aguda superior', 'Acute upper respiratory infection', 'Respiratorias', False, False),
        ('J45', 'Asma', 'Asthma', 'Respiratorias', False, False),
        ('E11', 'Diabetes mellitus tipo 2', 'Type 2 diabetes', 'Crónicas', False, False),
        ('I10', 'Hipertensión esencial', 'Essential hypertension', 'Crónicas', False, False),
        ('E44', 'Desnutrición proteico-calórica moderada', 'Moderate malnutrition', 'Nutricionales', True, False),
        ('E86', 'Deshidratación', 'Dehydration', 'Nutricionales', False, False),
        ('O80', 'Parto único espontáneo', 'Spontaneous delivery', 'Obstetricia', False, False),
        ('Z34', 'Supervisión de embarazo normal', 'Normal pregnancy supervision', 'Obstetricia', False, False),
        ('S06', 'Traumatismo intracraneal', 'Intracranial injury', 'Traumatismos', False, False),
        ('T14', 'Traumatismo no especificado', 'Unspecified injury', 'Traumatismos', False, False),
        ('K29', 'Gastritis y duodenitis', 'Gastritis', 'Digestivas', False, False),
        ('N39', 'Infección de vías urinarias', 'Urinary tract infection', 'Genitourinarias', False, False),
        ('L08', 'Infección local de piel', 'Local skin infection', 'Dermatológicas', False, False),
        ('H10', 'Conjuntivitis', 'Conjunctivitis', 'Oftalmológicas', False, False),
    ]
    for codigo, es, en, cat, notif, trop in enfermedades:
        db.session.add(Enfermedad(codigo_icd10=codigo, nombre_es=es, nombre_en=en,
                                   categoria=cat, es_notificable=notif, es_tropical=trop))
    db.session.commit()
    print(f"  ✓ {len(enfermedades)} enfermedades ICD-10 (catálogo inicial)")
    print("    Nota: el catálogo ICD-10 completo se importa con scripts/importar_icd10.py")


def seed_sintomas():
    """Síntomas comunes para registro de consultas."""
    if Sintoma.query.first():
        print("  · Síntomas ya cargados — omitiendo")
        return

    sintomas = [
        ('Fiebre', 'Fever', 'general'),
        ('Cefalea', 'Headache', 'neurológico'),
        ('Tos', 'Cough', 'respiratorio'),
        ('Tos con expectoración', 'Productive cough', 'respiratorio'),
        ('Dificultad respiratoria', 'Dyspnea', 'respiratorio'),
        ('Dolor torácico', 'Chest pain', 'cardiovascular'),
        ('Diarrea', 'Diarrhea', 'gastrointestinal'),
        ('Vómitos', 'Vomiting', 'gastrointestinal'),
        ('Náuseas', 'Nausea', 'gastrointestinal'),
        ('Dolor abdominal', 'Abdominal pain', 'gastrointestinal'),
        ('Escalofríos', 'Chills', 'general'),
        ('Sudoración nocturna', 'Night sweats', 'general'),
        ('Fatiga', 'Fatigue', 'general'),
        ('Pérdida de peso', 'Weight loss', 'general'),
        ('Pérdida de apetito', 'Loss of appetite', 'general'),
        ('Dolor muscular', 'Myalgia', 'musculoesquelético'),
        ('Dolor articular', 'Arthralgia', 'musculoesquelético'),
        ('Erupción cutánea', 'Skin rash', 'dermatológico'),
        ('Picazón', 'Pruritus', 'dermatológico'),
        ('Mareos', 'Dizziness', 'neurológico'),
        ('Convulsiones', 'Seizures', 'neurológico'),
        ('Rigidez de cuello', 'Neck stiffness', 'neurológico'),
        ('Dolor al orinar', 'Dysuria', 'genitourinario'),
        ('Sangrado', 'Bleeding', 'general'),
        ('Ictericia', 'Jaundice', 'general'),
        ('Edema', 'Edema', 'general'),
        ('Palpitaciones', 'Palpitations', 'cardiovascular'),
        ('Visión borrosa', 'Blurred vision', 'oftalmológico'),
        ('Dolor de garganta', 'Sore throat', 'respiratorio'),
        ('Congestión nasal', 'Nasal congestion', 'respiratorio'),
    ]
    for es, en, cat in sintomas:
        db.session.add(Sintoma(nombre_es=es, nombre_en=en, categoria=cat))
    db.session.commit()
    print(f"  ✓ {len(sintomas)} síntomas")


def seed_instalaciones():
    """Instalaciones sanitarias iniciales (se amplían por provincia al desplegar)."""
    if Instalacion.query.first():
        print("  · Instalaciones ya cargadas — omitiendo")
        return

    malabo = Distrito.query.filter_by(codigo='MAL').first()
    bata = Distrito.query.filter_by(codigo='BAT').first()
    pale = Distrito.query.filter_by(codigo='PAL').first()

    instalaciones = [
        ('HGM-001', 'Hospital General de Malabo', 'hospital', malabo, 3.7504, 8.7371),
        ('HRB-001', 'Hospital Regional de Bata', 'hospital', bata, 1.8639, 9.7658),
        ('CSA-001', 'Centro de Salud de Annobón', 'clinica', pale, -1.4068, 5.6322),
    ]
    for codigo, nombre, tipo, distrito, lat, lng in instalaciones:
        db.session.add(Instalacion(
            codigo=codigo, nombre=nombre, tipo=tipo,
            distrito_id=distrito.id if distrito else None,
            latitud=lat, longitud=lng,
        ))
    db.session.commit()
    print(f"  ✓ {len(instalaciones)} instalaciones iniciales")


def seed_usuario_admin():
    """
    Crea el usuario administrador inicial y el usuario sistema de sync.

    SEGURIDAD: la contraseña del admin se genera aleatoriamente y se
    muestra UNA SOLA VEZ en consola. Cámbiela en el primer acceso.
    Se puede fijar con la variable de entorno ADMIN_INITIAL_PASSWORD.
    """
    creados = []

    if not Usuario.query.filter_by(nombre_usuario='admin').first():
        password = os.environ.get('ADMIN_INITIAL_PASSWORD') or secrets.token_urlsafe(12)
        admin = Usuario(
            nombre_usuario='admin',
            nombre_completo='Administrador del Sistema',
            rol='superadmin',
        )
        admin.set_password(password)
        db.session.add(admin)
        creados.append(('admin', password))

    if not Usuario.query.filter_by(nombre_usuario='sistema_sync').first():
        # Usuario interno para atribuir consultas importadas vía sync.
        # No puede iniciar sesión: password aleatoria nunca revelada.
        sistema = Usuario(
            nombre_usuario='sistema_sync',
            nombre_completo='Sistema — Sincronización Externa',
            rol='recepcion',
            activo=False,   # No puede hacer login
        )
        sistema.set_password(secrets.token_urlsafe(32))
        db.session.add(sistema)
        creados.append(('sistema_sync', '(interno — sin acceso)'))

    db.session.commit()

    for usuario, password in creados:
        if usuario == 'admin':
            print(f"  ✓ Usuario admin creado")
            print(f"    ┌─────────────────────────────────────────────┐")
            print(f"    │  USUARIO:    admin                          │")
            print(f"    │  CONTRASEÑA: {password:<30} │")
            print(f"    │  ⚠ Anótela — no se volverá a mostrar.       │")
            print(f"    │  ⚠ Cámbiela en el primer inicio de sesión.  │")
            print(f"    └─────────────────────────────────────────────┘")
        else:
            print(f"  ✓ Usuario {usuario} creado {password}")

    if not creados:
        print("  · Usuarios base ya existen — omitiendo")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def seed_todo():
    print("\nBIOKO HEALTH — Carga inicial de datos")
    print("─" * 50)
    seed_geografia()
    seed_provincias()
    seed_enfermedades()
    seed_sintomas()
    seed_instalaciones()
    seed_usuario_admin()
    print("─" * 50)
    print("✓ Seed completado.\n")


if __name__ == '__main__':
    from app import create_app
    app = create_app(os.environ.get('FLASK_ENV', 'production'))
    with app.app_context():
        db.create_all()
        seed_todo()
