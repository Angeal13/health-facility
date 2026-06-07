# 🏥 Bioko Health — Instalación Sanitaria

**Hospital / Clínica / Puesto de Salud — República de Guinea Ecuatorial**

Un único repositorio para todos los tipos de instalación sanitaria.
`FACILITY_TYPE` en `.env` determina qué módulos aparecen.

## Tipos de instalación

```env
FACILITY_TYPE=hospital   # Todos los módulos clínicos
FACILITY_TYPE=clinica    # Módulos generales sin especialidades
FACILITY_TYPE=puesto     # Básico: consultas, vacunas, urgencias
```

## Instalar

```bash
# 1. Configurar
cp .env.template .env
# Editar:
#   FACILITY_CODE=HMGE-001         (código único de esta instalación)
#   FACILITY_NAME=Hospital General  (nombre completo)
#   FACILITY_TYPE=hospital
#   PROVINCIAL_NODE_URL=http://10.10.0.1:5000  (IP del nodo provincial)
#   SYNC_API_TOKEN=<mismo-token-en-toda-la-red>

# 2. Instalar
sudo bash instalar.sh
```

El instalador configura automáticamente:
- Python, MySQL, Nginx, Gunicorn
- WiFi DHCP para tablets (dnsmasq)
- Firewall: tablets sin acceso a internet
- Servicio systemd + backup cron diario

## Desarrollo local

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.template .env            # FLASK_ENV=development usa SQLite
python scripts/seed_db.py
python run.py                    # → http://localhost:5000
```

## Comunicación

| Origen | Destino | Red |
|--------|---------|-----|
| Tablets / PCs del personal | Este servidor (mini-PC) | WiFi local del edificio |
| Este servidor | Nodo Provincial | Intranet provincial |
| Tablets | Internet | ❌ Bloqueado por firewall |

Este servidor **nunca** habla directamente con el Ministerio
ni con otras instalaciones. Todo pasa por el nodo provincial.

## Repos relacionados

- [`bioko-health-ministerio`](../bioko-health-ministerio)
- [`bioko-health-nodo-provincial`](../bioko-health-nodo-provincial)
- [`bioko-health-annobon`](../bioko-health-annobon)
