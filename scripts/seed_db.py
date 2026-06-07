"""
Script de inicialización de la base de datos.
Carga: regiones, distritos, barrios de Bioko Island, catálogo ICD-10 enfermedades tropicales,
síntomas, usuario admin inicial.
Ejecutar: python scripts/seed_db.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.models import (db, Region, Distrito, Barrio, Enfermedad, Sintoma,
                                Instalacion, Usuario)

app = create_app('development')


def seed_geografia():
    print("📍 Cargando geografía de Guinea Ecuatorial...")

    # Regiones
    bioko_norte = Region(nombre='Bioko Norte', codigo='BN', isla=True)
    bioko_sur = Region(nombre='Bioko Sur', codigo='BS', isla=True)
    litoral = Region(nombre='Litoral', codigo='LT', isla=False)
    centro_sur = Region(nombre='Centro Sur', codigo='CS', isla=False)
    kie_ntem = Region(nombre='Kié-Ntem', codigo='KN', isla=False)
    wele_nzas = Region(nombre='Wele-Nzas', codigo='WN', isla=False)
    annobon = Region(nombre='Annobón', codigo='AN', isla=True)

    for r in [bioko_norte, bioko_sur, litoral, centro_sur, kie_ntem, wele_nzas, annobon]:
        db.session.add(r)
    db.session.flush()

    # Distritos Bioko Norte
    malabo = Distrito(nombre='Malabo', codigo='BN-MAL', region_id=bioko_norte.id,
                      latitud=3.7504, longitud=8.7371)
    punta_europa = Distrito(nombre='Punta Europa', codigo='BN-PE', region_id=bioko_norte.id,
                             latitud=3.7800, longitud=8.7600)
    basilé = Distrito(nombre='Basile', codigo='BN-BAS', region_id=bioko_norte.id,
                      latitud=3.8200, longitud=8.8000)

    # Distritos Bioko Sur
    luba = Distrito(nombre='Luba', codigo='BS-LUB', region_id=bioko_sur.id,
                    latitud=3.4553, longitud=8.5470)
    riaba = Distrito(nombre='Riaba', codigo='BS-RIA', region_id=bioko_sur.id,
                     latitud=3.6000, longitud=8.9000)
    moka = Distrito(nombre='Moka', codigo='BS-MOK', region_id=bioko_sur.id,
                    latitud=3.6200, longitud=8.7500)

    # Río Muni (continental)
    bata = Distrito(nombre='Bata', codigo='LT-BAT', region_id=litoral.id,
                    latitud=1.8639, longitud=9.7717)
    ebebiyin = Distrito(nombre='Ebebiyin', codigo='KN-EBE', region_id=kie_ntem.id,
                        latitud=2.1500, longitud=11.3352)
    evinayong = Distrito(nombre='Evinayong', codigo='CS-EVI', region_id=centro_sur.id,
                         latitud=1.4470, longitud=10.5671)

    for d in [malabo, punta_europa, basilé, luba, riaba, moka, bata, ebebiyin, evinayong]:
        db.session.add(d)
    db.session.flush()

    # Barrios de Malabo
    barrios_malabo = [
        ('Centro', 3.7504, 8.7371, 8500),
        ('Ela Nguema', 3.7600, 8.7450, 12000),
        ('Nueva Pinta', 3.7350, 8.7250, 9000),
        ('Aeropuerto', 3.7200, 8.7100, 5500),
        ('Caracolas', 3.7450, 8.7600, 7000),
        ('Bata Road', 3.7550, 8.7500, 6200),
        ('Campo Yaoundé', 3.7650, 8.7350, 4800),
        ('Comandechina', 3.7400, 8.7300, 5000),
        ('Decroly', 3.7480, 8.7420, 3500),
        ('Loma Luz', 3.7520, 8.7480, 4200),
    ]

    for nombre, lat, lng, pob in barrios_malabo:
        b = Barrio(nombre=nombre, distrito_id=malabo.id, latitud=lat,
                   longitud=lng, poblacion_estimada=pob)
        db.session.add(b)

    # Barrios de Luba
    barrios_luba = [
        ('Centro Luba', 3.4553, 8.5470, 3500),
        ('Puerto Luba', 3.4500, 8.5400, 2800),
    ]
    for nombre, lat, lng, pob in barrios_luba:
        b = Barrio(nombre=nombre, distrito_id=luba.id, latitud=lat,
                   longitud=lng, poblacion_estimada=pob)
        db.session.add(b)

    db.session.commit()
    print(f"   ✓ Regiones, distritos y barrios cargados.")


def seed_enfermedades():
    print("🦠 Cargando catálogo de enfermedades ICD-10...")

    enfermedades = [
        # ─ Enfermedades tropicales e infecciosas prioritarias ─
        ('A00', 'Cólera', 'Infecciosas y parasitarias', True, True),
        ('A01', 'Fiebre tifoidea y paratifoidea', 'Infecciosas y parasitarias', True, True),
        ('A06', 'Amebiasis', 'Infecciosas y parasitarias', False, True),
        ('A09', 'Diarrea y gastroenteritis infecciosa', 'Infecciosas y parasitarias', False, False),
        ('A15', 'Tuberculosis respiratoria', 'Infecciosas y parasitarias', True, True),
        ('A17', 'Tuberculosis del sistema nervioso', 'Infecciosas y parasitarias', True, True),
        ('A20', 'Peste', 'Infecciosas y parasitarias', True, True),
        ('A22', 'Ántrax', 'Infecciosas y parasitarias', True, False),
        ('A34', 'Tétanos obstétrico', 'Infecciosas y parasitarias', True, True),
        ('A35', 'Tétanos', 'Infecciosas y parasitarias', True, True),
        ('A36', 'Difteria', 'Infecciosas y parasitarias', True, False),
        ('A37', 'Tos ferina', 'Infecciosas y parasitarias', True, False),
        ('A39', 'Meningitis meningocócica', 'Infecciosas y parasitarias', True, False),
        ('A50', 'Sífilis congénita', 'Infecciosas y parasitarias', True, False),
        ('A63', 'Enfermedades de transmisión sexual', 'Infecciosas y parasitarias', False, False),
        ('A77', 'Fiebre manchada (Rickettsia)', 'Infecciosas y parasitarias', True, True),
        ('A82', 'Rabia', 'Infecciosas y parasitarias', True, True),
        ('A87', 'Meningitis viral', 'Infecciosas y parasitarias', True, False),
        ('A90', 'Dengue sin complicaciones', 'Infecciosas y parasitarias', True, True),
        ('A91', 'Fiebre del dengue hemorrágico', 'Infecciosas y parasitarias', True, True),
        ('A92', 'Otras enfermedades febriles por arbovirus', 'Infecciosas y parasitarias', True, True),
        ('A96', 'Fiebre hemorrágica por arenavirus (Lassa)', 'Infecciosas y parasitarias', True, True),
        ('A98', 'Ébola / Fiebre hemorrágica viral', 'Infecciosas y parasitarias', True, True),
        ('B00', 'Infección por herpes simple', 'Infecciosas y parasitarias', False, False),
        ('B01', 'Varicela', 'Infecciosas y parasitarias', True, False),
        ('B05', 'Sarampión', 'Infecciosas y parasitarias', True, False),
        ('B06', 'Rubéola', 'Infecciosas y parasitarias', True, False),
        ('B15', 'Hepatitis A', 'Infecciosas y parasitarias', True, True),
        ('B16', 'Hepatitis B aguda', 'Infecciosas y parasitarias', True, True),
        ('B18', 'Hepatitis B crónica', 'Infecciosas y parasitarias', True, True),
        ('B20', 'VIH/SIDA', 'Infecciosas y parasitarias', True, False),
        ('B50', 'Malaria por Plasmodium falciparum', 'Infecciosas y parasitarias', True, True),
        ('B51', 'Malaria por Plasmodium vivax', 'Infecciosas y parasitarias', True, True),
        ('B52', 'Malaria por Plasmodium malariae', 'Infecciosas y parasitarias', True, True),
        ('B53', 'Otras malarias', 'Infecciosas y parasitarias', True, True),
        ('B55', 'Leishmaniasis', 'Infecciosas y parasitarias', True, True),
        ('B56', 'Tripanosomiasis africana (Enfermedad del sueño)', 'Infecciosas y parasitarias', True, True),
        ('B65', 'Esquistosomiasis', 'Infecciosas y parasitarias', True, True),
        ('B68', 'Teniasis', 'Infecciosas y parasitarias', False, True),
        ('B73', 'Oncocercosis (Ceguera del río)', 'Infecciosas y parasitarias', True, True),
        ('B74', 'Filariasis linfática', 'Infecciosas y parasitarias', True, True),
        ('B76', 'Anquilostomiasis', 'Infecciosas y parasitarias', False, True),
        ('B77', 'Ascariasis', 'Infecciosas y parasitarias', False, True),
        # ─ Respiratorias ─
        ('J00', 'Rinofaringitis aguda (resfriado común)', 'Respiratorias', False, False),
        ('J06', 'Infección aguda vías respiratorias superiores', 'Respiratorias', False, False),
        ('J11', 'Influenza (gripe)', 'Respiratorias', True, False),
        ('J18', 'Neumonía bacteriana', 'Respiratorias', False, False),
        ('J20', 'Bronquitis aguda', 'Respiratorias', False, False),
        ('J45', 'Asma', 'Respiratorias', False, False),
        ('J47', 'Bronquiectasia', 'Respiratorias', False, False),
        # ─ Digestivas ─
        ('K29', 'Gastritis', 'Digestivas', False, False),
        ('K35', 'Apendicitis aguda', 'Digestivas', False, False),
        ('K50', 'Enfermedad de Crohn', 'Digestivas', False, False),
        ('K74', 'Cirrosis hepática', 'Digestivas', False, False),
        # ─ Cardiovasculares ─
        ('I10', 'Hipertensión esencial', 'Cardiovasculares', False, False),
        ('I21', 'Infarto agudo de miocardio', 'Cardiovasculares', False, False),
        ('I50', 'Insuficiencia cardíaca', 'Cardiovasculares', False, False),
        ('I63', 'Infarto cerebral (ACV)', 'Cardiovasculares', True, False),
        # ─ Metabólicas ─
        ('E11', 'Diabetes mellitus tipo 2', 'Metabólicas', False, False),
        ('E10', 'Diabetes mellitus tipo 1', 'Metabólicas', False, False),
        ('E43', 'Desnutrición proteico-calórica grave', 'Metabólicas', True, True),
        ('E44', 'Desnutrición proteico-calórica moderada', 'Metabólicas', True, True),
        ('E55', 'Deficiencia de vitamina D', 'Metabólicas', False, False),
        # ─ Materno-infantil ─
        ('O15', 'Eclampsia', 'Materno-infantil', True, False),
        ('O36', 'Atención materna por problemas fetales', 'Materno-infantil', False, False),
        ('P07', 'Bajo peso al nacer', 'Materno-infantil', True, False),
        ('P21', 'Asfixia del nacimiento', 'Materno-infantil', True, False),
        # ─ Piel ─
        ('L00', 'Síndrome estafilocócico de piel escaldada', 'Piel', False, False),
        ('L03', 'Celulitis', 'Piel', False, False),
        ('L20', 'Dermatitis atópica (eczema)', 'Piel', False, False),
        ('L50', 'Urticaria', 'Piel', False, False),
        # ─ Trauma ─
        ('S00', 'Traumatismo superficial de cabeza', 'Traumatología', False, False),
        ('S72', 'Fractura del fémur', 'Traumatología', False, False),
        ('T14', 'Traumatismo de región no especificada', 'Traumatología', False, False),
        ('T30', 'Quemaduras', 'Traumatología', False, False),
    ]

    for codigo, nombre, cat, notif, tropical in enfermedades:
        if not Enfermedad.query.filter_by(codigo_icd10=codigo).first():
            e = Enfermedad(
                codigo_icd10=codigo,
                nombre_es=nombre,
                categoria=cat,
                es_notificable=notif,
                es_tropical=tropical
            )
            db.session.add(e)

    db.session.commit()
    print(f"   ✓ {len(enfermedades)} enfermedades cargadas.")


def seed_sintomas():
    print("🤒 Cargando catálogo de síntomas...")

    sintomas = [
        ('Fiebre', 'General'), ('Escalofríos', 'General'), ('Malestar general', 'General'),
        ('Fatiga / Cansancio', 'General'), ('Pérdida de peso', 'General'), ('Sudoración nocturna', 'General'),
        ('Dolor de cabeza (cefalea)', 'Neurológico'), ('Mareos / Vértigo', 'Neurológico'),
        ('Convulsiones', 'Neurológico'), ('Confusión mental', 'Neurológico'), ('Rigidez de nuca', 'Neurológico'),
        ('Pérdida de conciencia', 'Neurológico'),
        ('Tos', 'Respiratorio'), ('Disnea / Dificultad respiratoria', 'Respiratorio'),
        ('Dolor torácico', 'Respiratorio'), ('Hemoptisis (sangre en esputo)', 'Respiratorio'),
        ('Congestión nasal', 'Respiratorio'), ('Dolor de garganta', 'Respiratorio'),
        ('Náuseas', 'Gastrointestinal'), ('Vómitos', 'Gastrointestinal'), ('Diarrea', 'Gastrointestinal'),
        ('Diarrea con sangre', 'Gastrointestinal'), ('Dolor abdominal', 'Gastrointestinal'),
        ('Distensión abdominal', 'Gastrointestinal'), ('Ictericia (coloración amarilla)', 'Gastrointestinal'),
        ('Sangrado rectal', 'Gastrointestinal'),
        ('Exantema / Sarpullido', 'Piel'), ('Prurito / Picazón', 'Piel'), ('Heridas / Úlceras', 'Piel'),
        ('Edema / Hinchazón', 'Piel'),
        ('Poliuria (orina excesiva)', 'Urinario'), ('Disuria (dolor al orinar)', 'Urinario'),
        ('Hematuria (sangre en orina)', 'Urinario'),
        ('Dolor articular', 'Musculoesquelético'), ('Dolor muscular', 'Musculoesquelético'),
        ('Debilidad muscular', 'Musculoesquelético'),
        ('Hemorragia vaginal anormal', 'Ginecológico'), ('Contracciones uterinas', 'Ginecológico'),
        ('Visión borrosa', 'Oftalmológico'), ('Fotofobia', 'Oftalmológico'),
        ('Sangrado inusual', 'Hemorrágico'), ('Petequias / manchas rojas en piel', 'Hemorrágico'),
        ('Palidez / Anemia', 'Hemorrágico'),
    ]

    for nombre, cat in sintomas:
        if not Sintoma.query.filter_by(nombre_es=nombre).first():
            db.session.add(Sintoma(nombre_es=nombre, categoria=cat))

    db.session.commit()
    print(f"   ✓ {len(sintomas)} síntomas cargados.")


def seed_instalaciones():
    print("🏥 Cargando instalaciones sanitarias...")

    from app.models.models import Distrito
    malabo = Distrito.query.filter_by(codigo='BN-MAL').first()
    luba = Distrito.query.filter_by(codigo='BS-LUB').first()
    bata = Distrito.query.filter_by(codigo='LT-BAT').first()

    instalaciones_data = [
        ('HMGE', 'Hospital General de Malabo', 'hospital', malabo, 3.7504, 8.7371),
        ('HRB', 'Hospital Regional de Bioko', 'hospital', malabo, 3.7550, 8.7420),
        ('CSM-ENG', 'Centro de Salud Ela Nguema', 'clinica', malabo, 3.7600, 8.7450),
        ('CSM-MON', 'Centro de Salud Mondoasi', 'clinica', malabo, 3.7400, 8.7300),
        ('PS-BAS', 'Puesto de Salud Basilé', 'puesto', None, 3.8200, 8.8000),
        ('HL', 'Hospital de Luba', 'hospital', luba, 3.4553, 8.5470),
        ('HB', 'Hospital Regional de Bata', 'hospital', bata, 1.8639, 9.7717),
    ]

    for codigo, nombre, tipo, distrito, lat, lng in instalaciones_data:
        if not Instalacion.query.filter_by(codigo=codigo).first():
            inst = Instalacion(
                codigo=codigo,
                nombre=nombre,
                tipo=tipo,
                distrito_id=distrito.id if distrito else None,
                latitud=lat,
                longitud=lng
            )
            db.session.add(inst)

    db.session.commit()
    print(f"   ✓ {len(instalaciones_data)} instalaciones cargadas.")


def seed_usuario_admin():
    print("👤 Creando usuario administrador...")

    if not Usuario.query.filter_by(nombre_usuario='admin').first():
        u = Usuario(
            nombre_usuario='admin',
            nombre_completo='Administrador del Sistema',
            rol='superadmin',
            email='admin@biokohealth.gq',
        )
        u.set_password('Bioko2024!')
        db.session.add(u)
        db.session.commit()
        print("   ✓ Usuario: admin / Contraseña: Bioko2024!")
        print("   ⚠️  CAMBIAR LA CONTRASEÑA INMEDIATAMENTE EN PRODUCCIÓN")
    else:
        print("   - Usuario admin ya existe.")


if __name__ == '__main__':
    with app.app_context():
        print("\n🚀 Inicializando base de datos Bioko Health...\n")
        db.create_all()
        seed_geografia()
        seed_provincias()
        seed_enfermedades()
        seed_sintomas()
        seed_instalaciones()
        seed_usuario_admin()
        print("\n✅ Base de datos inicializada correctamente.\n")
        print("Para ejecutar el sistema:")
        print("  python run.py\n")
        print("Acceder en: http://localhost:5000")
        print("Usuario: admin  |  Contraseña: Bioko2024!\n")


def seed_provincias():
    """Siembra las 6 provincias / territorios de Guinea Ecuatorial."""
    from app.models.models import Provincia
    print("🗺️ Cargando provincias de Guinea Ecuatorial...")

    provincias = [
        # codigo,  nombre,         sede,               isla,  nodo_codigo
        ('BN-BS', 'Bioko',          'Malabo',           True,  'NODO-BIOKO'),
        ('AN',    'Annobón',        'San Antonio de Palé', True, 'NODO-ANNOBON'),
        ('LT',    'Litoral',        'Bata',             False, 'NODO-LITORAL'),
        ('CS',    'Centro Sur',     'Evinayong',        False, 'NODO-CENTROSUR'),
        ('KN',    'Kié-Ntem',       'Ebebiyín',         False, 'NODO-KIENTEM'),
        ('WN',    'Wele-Nzas',      'Mongomo',          False, 'NODO-WELENZAS'),
    ]

    for codigo, nombre, sede, isla, nodo_codigo in provincias:
        if not Provincia.query.filter_by(codigo=codigo).first():
            db.session.add(Provincia(
                codigo=codigo, nombre=nombre,
                sede=sede, isla=isla,
                nodo_codigo=nodo_codigo
            ))

    db.session.commit()
    print(f"   ✓ 6 provincias cargadas.")
