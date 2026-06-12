# BIOKO HEALTH

Sistema Nacional de Historia Clínica Electrónica y Vigilancia Epidemiológica
para la República de Guinea Ecuatorial.

**Un solo código — cuatro modos de despliegue** controlados por `FACILITY_MODE`:

| Modo | Descripción | Plantilla .env |
|---|---|---|
| `facility` | Instalación sanitaria (hospital/clínica/puesto) | `env-templates/instalacion.env.template` |
| `provincial_node` | Nodo provincial (1 por provincia) | `env-templates/nodo-provincial.env.template` |
| `central_server` | Servidor central del Ministerio (único) | `env-templates/central-ministerio.env.template` |
| `annobon_node` | Nodo especial de Annobón (conectividad intermitente) | `env-templates/annobon.env.template` |

---

## Arquitectura

```
                    ┌──────────────────────────┐
   NIVEL 1          │  SERVIDOR CENTRAL        │
                    │  Ministerio — Malabo     │
                    └────────────┬─────────────┘
                                 │  WAN segura (TLS + token HMAC)
            ┌────────────────────┼────────────────────┐
   NIVEL 2  │                    │                    │
      ┌─────┴─────┐       ┌──────┴──────┐      ┌──────┴──────┐
      │ Nodo Prov. │       │ Nodo Prov.  │      │ Nodo Annobón│
      │ Bioko Norte│  ...  │ Litoral     │      │ (intermit.) │
      └─────┬─────┘       └──────┬──────┘      └──────┬──────┘
            │ Fibra óptica intranet provincial        │
   NIVEL 3  │                    │                    │
      ┌─────┴────┐         ┌─────┴────┐         ┌─────┴────┐
      │ Hospital │         │ Clínica  │         │ Puesto   │
      └──────────┘         └──────────┘         └──────────┘
```

- **Intranet provincial (fibra óptica):** sincronización en tiempo real
  (push inmediato + pull cada 30 s) entre instalaciones y su nodo provincial.
- **WAN nacional:** solicitud de expedientes entre provincias, alertas
  epidemiológicas al nivel central, sync nocturno de respaldo (02:00).
- **Offline-first:** toda instalación opera sin red; los datos se encolan
  y sincronizan automáticamente al recuperarse el enlace.

---

## Instalación en producción (Ubuntu Server 22.04+)

### 1. Preparar el servidor

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv \
    mysql-server nginx git

# Usuario de servicio sin shell
sudo useradd -r -s /usr/sbin/nologin -d /opt/bioko-health bioko
```

### 2. Base de datos

```bash
sudo mysql << 'SQL'
CREATE DATABASE bioko_health CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;
CREATE USER 'bioko_user'@'localhost' IDENTIFIED BY 'CAMBIAR_ESTE_PASSWORD';
GRANT ALL PRIVILEGES ON bioko_health.* TO 'bioko_user'@'localhost';
FLUSH PRIVILEGES;
SQL
```

### 3. Aplicación

```bash
sudo mkdir -p /opt/bioko-health
sudo chown bioko:bioko /opt/bioko-health
# Copiar el código a /opt/bioko-health (git clone o scp del zip)

cd /opt/bioko-health
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt

# Configuración — elegir la plantilla del tipo de nodo:
cp env-templates/instalacion.env.template .env
nano .env   # Completar SECRET_KEY, DATABASE_URL, FACILITY_CODE, tokens

# Generar SECRET_KEY:
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Inicializar la base de datos

```bash
./venv/bin/python scripts/seed_db.py
# ⚠ ANOTAR la contraseña del admin que se muestra — solo se muestra una vez
```

### 5. Servicio y proxy

```bash
sudo cp deploy/bioko-health.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bioko-health

sudo cp deploy/nginx-bioko.conf /etc/nginx/sites-available/bioko-health
sudo ln -s /etc/nginx/sites-available/bioko-health /etc/nginx/sites-enabled/
# Colocar certificados TLS en /etc/ssl/bioko/ (ver nota abajo)
sudo nginx -t && sudo systemctl reload nginx
```

### 6. Backup automático

```bash
sudo crontab -e
# Añadir (backup diario 01:30, antes del sync de las 02:00):
30 1 * * * /opt/bioko-health/deploy/backup_db.sh >> /opt/bioko-health/logs/backup.log 2>&1
```

### Certificados TLS

- **Intranet provincial:** usar una CA interna del proyecto (los nodos no
  tienen dominio público). Generar con `openssl` o `mkcert` y distribuir
  la CA raíz a los navegadores de las instalaciones.
- **Servidor central (dominio público):** `sudo certbot --nginx -d central.biokohealth.gq`

---

## Seguridad incorporada

| Control | Implementación |
|---|---|
| Passwords | bcrypt (Flask-Bcrypt) |
| CSRF | Flask-WTF en todos los formularios; API de sync exenta (usa tokens HMAC) |
| Fuerza bruta | Rate limiting en login: 10 intentos/min por IP (Flask-Limiter) |
| Open redirect | Validación de `next` contra host propio |
| Sesiones | Timeout 8 h inactividad, cookies HttpOnly + Secure + SameSite |
| Entre nodos | Token HMAC compartido (`X-Bioko-Token`), comparación constant-time |
| Transporte | TLS terminado en nginx; HSTS activo |
| Cabeceras | X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| Roles | 7 niveles; escritura clínica restringida a médico/enfermero |
| Auditoría | Log de accesos fallidos con IP; RegistroSync de toda operación |

---

## Desarrollo local

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp env-templates/instalacion.env.template .env
# Editar .env: SECRET_KEY=cualquier-valor-dev, dejar DATABASE_URL vacío (usa SQLite)
sed -i 's|^DATABASE_URL=.*|# DATABASE_URL no definido → SQLite local|' .env
FLASK_ENV=development python scripts/seed_db.py
FLASK_ENV=development python run.py
# → http://localhost:5000
```

## Estructura del proyecto

```
bioko-health/
├── app/
│   ├── __init__.py          # Application factory (create_app)
│   ├── models/models.py     # Modelos SQLAlchemy (3 niveles)
│   ├── routes/              # Blueprints: auth, pacientes, consultas,
│   │                        # epidemiología, sync, provincial, admin...
│   ├── templates/           # Jinja2 (todas las vistas)
│   └── utils/               # Motores de sync, generador de PDFs
├── scripts/seed_db.py       # Carga inicial de catálogos
├── deploy/                  # nginx, gunicorn, systemd, backup
├── env-templates/           # Plantillas .env por tipo de nodo
├── config.py                # Configuración central
├── wsgi.py                  # Entrada producción (gunicorn)
├── run.py                   # Entrada desarrollo
└── requirements.txt
```

---

**BP Tecnología S.L.** — Malabo, Guinea Ecuatorial
Documento interno. Sistema desarrollado para el Ministerio de Sanidad y Bienestar Social.
