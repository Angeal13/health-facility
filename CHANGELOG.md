# Changelog — Instalación Sanitaria

All notable changes to Bioko Health are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2026-05-30

### Initial production release — Bioko Island pilot

#### Added
- **Historia Clínica Digital** — expediente completo con diagnósticos ICD-10,
  prescripciones, signos vitales, alergias, vacunación
- **Gestión de Pacientes** — registro, búsqueda, lista paginada, edición
- **Consultas Médicas** — formulario completo con síntomas, diagnósticos ICD-10,
  prescripciones y exámenes de laboratorio
- **Vigilancia Epidemiológica** — alertas automáticas de brotes, tendencias,
  enfermedades notificables, mapa de dispersión (Leaflet.js offline)
- **Arquitectura de 3 niveles** — instalación → nodo provincial → Ministerio
- **Nodo Provincial** — dashboard epidemiológico de solo lectura para
  operadores del Ministerio; sirve expedientes vía intranet; enruta
  transferencias inter-provinciales vía internet
- **Sync periódico** — APScheduler, diario a las 02:00 AM (configurable)
- **Sync intranet** — motor de tiempo real para redes provinciales
- **Transferencia de expedientes** — misma provincia (intranet, segundos);
  distinta provincia (internet, bajo demanda, caché 30 días)
- **Generación de PDFs** — historia clínica y reporte epidemiológico (ReportLab)
- **Exportación OMS/DHIS2** — CSV compatible con sistemas internacionales
- **Panel de Red** — estado de todos los nodos, VPN, URL de acceso LAN
- **Panel de Administración** — usuarios, instalaciones, catálogo ICD-10
- **6 provincias** — Bioko, Litoral, Centro Sur, Kié-Ntem, Wele-Nzas + Annobón
  (pendiente decisión conectividad)
- **4 paquetes de despliegue** — Ministerio, Nodo Provincial (5 provincias),
  Instalación (hospital/clínica/puesto), Annobón
- **Instaladores automáticos** — `sudo bash instalar.sh` configura todo
  (Python, MySQL, Nginx, Gunicorn, UFW, DHCP, systemd, backup cron)
- **Backup automático** — `mysqldump` diario con rotación 30 días
- **Migraciones Alembic** — control de versiones del esquema de BD
- **Seguridad** — Flask-Limiter (brute force), session timeout 8h,
  CSRF tokens, bcrypt passwords, session_protection=strong
- **Errores** — páginas 404/403/500/429 en español
- **Datos iniciales** — geografía completa de Guinea Ecuatorial,
  75 enfermedades ICD-10 priorizadas para GQ, 43 síntomas,
  7 instalaciones de Bioko Island, 6 provincias

#### Supported deployment modes
- `installation` — hospital, clínica, puesto de salud
- `provincial_node` — nodo provincial (uno por provincia)
- `central_server` — servidor central del Ministerio
- `annobon_node` — Annobón (conectividad pendiente)

---

## [Unreleased]

### Planned
- Tests unitarios (pytest)
- Módulo de vacunación con calendario por edad
- Módulo de gestión de farmacia
- App móvil offline (PWA)
- Extensión a Río Muni (datos geográficos ya incluidos)
- Annobón — pendiente decisión del Ministerio sobre conectividad
