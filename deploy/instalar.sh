#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  BIOKO HEALTH — Instalación Sanitaria                           ║
# ║                                                                  ║
# ║  Instalar en el mini-PC de cada:                                 ║
# ║    • Hospital                                                    ║
# ║    • Centro de Salud                                             ║
# ║    • Puesto de Salud                                             ║
# ║                                                                  ║
# ║  El software es IDÉNTICO para los tres tipos.                   ║
# ║  Solo cambia FACILITY_TYPE y FACILITY_NAME en el .env.          ║
# ║                                                                  ║
# ║  Esta instalación habla ÚNICAMENTE con su nodo provincial.      ║
# ║  NUNCA directamente con otra instalación ni con el Ministerio.  ║
# ║                                                                  ║
# ║  Uso: sudo bash instalar.sh                                      ║
# ╚══════════════════════════════════════════════════════════════════╝
set -euo pipefail

VERDE='\033[0;32m'; AMARILLO='\033[1;33m'; ROJO='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${VERDE}✓ $1${NC}"; }
info() { echo -e "${AMARILLO}→ $1${NC}"; }
err()  { echo -e "${ROJO}✗ $1${NC}"; exit 1; }

[[ $EUID -ne 0 ]] && err "Ejecutar como root: sudo bash instalar.sh"
[[ ! -f "run.py" ]] && err "Ejecutar desde el directorio raíz del proyecto."

APP_DIR="/opt/bioko_health"
SERVICE_USER="bioko"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  BIOKO HEALTH — Instalación Sanitaria                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Tipo de instalación:"
echo "    [1] Hospital"
echo "    [2] Centro de Salud"
echo "    [3] Puesto de Salud"
echo ""
read -p "  Seleccionar tipo [1-3]: " TIPO_NUM
case "$TIPO_NUM" in
  1) FACILITY_TYPE="hospital";;
  2) FACILITY_TYPE="clinica";;
  3) FACILITY_TYPE="puesto";;
  *) err "Opción inválida." ;;
esac

read -p "  Nombre completo de esta instalación: " FACILITY_NAME
read -p "  Código único (ej: HMGE-001, CSM-ENG-001): " FACILITY_CODE

# ── Detectar interfaces ────────────────────────────────────────
INTERFACES=($(ip -o link show | awk -F': ' '{print $2}' | grep -v lo))
echo ""
for i in "${!INTERFACES[@]}"; do
    IP_IF=$(ip -4 addr show "${INTERFACES[$i]}" 2>/dev/null | grep -oP '(?<=inet )\S+' | cut -d/ -f1 || echo "sin IP")
    printf "    [%d] %-12s  %s\n" "$i" "${INTERFACES[$i]}" "$IP_IF"
done
echo ""
read -p "  Interfaz LAN para tablets del personal: " LAN_IDX
LAN_IFACE="${INTERFACES[$LAN_IDX]}"

read -p "  IP estática de este servidor en la LAN [192.168.X.10]: " LAN_IP
LAN_IP="${LAN_IP:-192.168.1.10}"
SUBNET=$(echo "$LAN_IP" | cut -d. -f1-3)

read -p "  IP del nodo provincial al que pertenece esta instalación: " PROV_NODE_IP

# ── Dependencias ───────────────────────────────────────────────
info "Instalando dependencias..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    nginx mysql-server \
    libmysqlclient-dev pkg-config build-essential \
    dnsmasq ufw curl net-tools
ok "Dependencias instaladas."

# ── IP estática ────────────────────────────────────────────────
info "Configurando IP estática $LAN_IP en $LAN_IFACE..."
cat > /etc/netplan/99-bioko-instalacion.yaml << NETPLAN
network:
  version: 2
  ethernets:
    ${LAN_IFACE}:
      dhcp4: false
      addresses: [${LAN_IP}/24]
      nameservers:
        addresses: [${LAN_IP}, 8.8.8.8]
NETPLAN
chmod 600 /etc/netplan/99-bioko-instalacion.yaml
netplan apply 2>/dev/null || true
ok "IP estática configurada."

# ── DHCP para tablets ──────────────────────────────────────────
info "Configurando DHCP para tablets (${SUBNET}.50–200)..."
cat > /etc/dnsmasq.d/bioko-lan.conf << DNSMASQ
interface=${LAN_IFACE}
bind-interfaces
dhcp-range=${SUBNET}.50,${SUBNET}.200,24h
dhcp-option=option:router,${LAN_IP}
dhcp-option=option:dns-server,${LAN_IP}
address=/salud.local/${LAN_IP}
address=/salud/${LAN_IP}
DNSMASQ
systemctl stop systemd-resolved 2>/dev/null || true
systemctl disable systemd-resolved 2>/dev/null || true
systemctl enable dnsmasq && systemctl restart dnsmasq
ok "DHCP activo — tablets recibirán IP automáticamente."

# ── Firewall ───────────────────────────────────────────────────
info "Configurando firewall..."
ufw --force reset > /dev/null 2>&1
ufw default deny incoming
ufw default allow outgoing
ufw allow in on "$LAN_IFACE" to any port 22  comment "SSH admin LAN"
ufw allow in on "$LAN_IFACE" to any port 80  comment "HTTP tablets"
ufw allow in on "$LAN_IFACE" to any port 53  comment "DNS tablets"
ufw allow in on "$LAN_IFACE" to any port 67  comment "DHCP tablets"
# Las tablets NO salen a internet — no se hace NAT
echo 0 > /proc/sys/net/ipv4/ip_forward
echo "net.ipv4.ip_forward = 0" > /etc/sysctl.d/99-bioko-noforward.conf
sysctl -p /etc/sysctl.d/99-bioko-noforward.conf > /dev/null 2>&1
ufw --force enable > /dev/null 2>&1
ok "Firewall: tablets sin internet, acceso solo al sistema local."

# ── Usuario sistema ────────────────────────────────────────────
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /bin/bash --home-dir "$APP_DIR" --create-home "$SERVICE_USER"
fi

# ── Copiar archivos ────────────────────────────────────────────
info "Copiando archivos..."
cp -r --no-preserve=ownership . "$APP_DIR/" 2>/dev/null || true
ok "Archivos copiados."

# ── Entorno Python ─────────────────────────────────────────────
info "Instalando entorno Python..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip wheel
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
ok "Entorno Python listo."

# ── .env ───────────────────────────────────────────────────────
if [[ ! -f "$APP_DIR/.env" ]]; then
    cp "$APP_DIR/deploy/instalacion/env.template" "$APP_DIR/.env"
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|GENERAR-python3.*|$SECRET|" "$APP_DIR/.env"
    sed -i "s|FACILITY_CODE=.*|FACILITY_CODE=$FACILITY_CODE|" "$APP_DIR/.env"
    sed -i "s|FACILITY_NAME=.*|FACILITY_NAME=$FACILITY_NAME|" "$APP_DIR/.env"
    sed -i "s|FACILITY_TYPE=.*|FACILITY_TYPE=$FACILITY_TYPE|" "$APP_DIR/.env"
    sed -i "s|LAN_HOST=.*|LAN_HOST=$LAN_IP|" "$APP_DIR/.env"
    sed -i "s|LAN_URL=.*|LAN_URL=http://$LAN_IP|" "$APP_DIR/.env"
    sed -i "s|PROVINCIAL_NODE_URL=.*|PROVINCIAL_NODE_URL=http://$PROV_NODE_IP:5000|" "$APP_DIR/.env"
    sed -i "s|INTRANET_CENTRAL_URL=.*|INTRANET_CENTRAL_URL=http://$PROV_NODE_IP:5000|" "$APP_DIR/.env"
    sed -i "s|CENTRAL_SERVER_URL=.*|CENTRAL_SERVER_URL=http://$PROV_NODE_IP:5000|" "$APP_DIR/.env"
    echo ""
    echo -e "${AMARILLO}  Editar: $APP_DIR/.env${NC}"
    echo "  Cambiar: SYNC_API_TOKEN (mismo token que el nodo provincial)"
    read -p "  ¿Listo? (s/N): " C
    [[ "$C" != "s" && "$C" != "S" ]] && err "Edite .env y vuelva a ejecutar."
fi

# ── MySQL ──────────────────────────────────────────────────────
info "Configurando MySQL..."
systemctl start mysql && systemctl enable mysql
cp "$APP_DIR/deploy/mysql_bioko.cnf" /etc/mysql/conf.d/bioko.cnf
systemctl restart mysql
DB_PASS="Bioko_$(openssl rand -hex 8)"
mysql -u root -e "
CREATE DATABASE IF NOT EXISTS bioko_health CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'bioko_user'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,INDEX,DROP ON bioko_health.* TO 'bioko_user'@'localhost';
FLUSH PRIVILEGES;" 2>/dev/null
sed -i "s|mysql+pymysql://bioko_user:PASSWORD_LOCAL@localhost|mysql+pymysql://bioko_user:${DB_PASS}@localhost|" "$APP_DIR/.env"
ok "MySQL configurado."

# ── Base de datos ──────────────────────────────────────────────
info "Inicializando base de datos..."
cd "$APP_DIR"
FLASK_ENV=installation "$APP_DIR/venv/bin/python" -c \
    "from app import create_app; from app.models.models import db; \
     app = create_app('installation'); app.app_context().push(); db.create_all()"
FLASK_ENV=installation "$APP_DIR/venv/bin/python" scripts/seed_db.py
ok "Base de datos lista."

# ── Gunicorn ───────────────────────────────────────────────────
cp "$APP_DIR/deploy/instalacion/gunicorn.conf.py" "$APP_DIR/gunicorn.conf.py"
sed -i "s|LAN_IP_PLACEHOLDER|$LAN_IP|" "$APP_DIR/gunicorn.conf.py"

# ── Nginx ──────────────────────────────────────────────────────
info "Configurando Nginx (solo LAN — tablets sin internet)..."
cp "$APP_DIR/deploy/instalacion/nginx" /etc/nginx/sites-available/bioko_health
sed -i "s|LAN_IP|$LAN_IP|g" /etc/nginx/sites-available/bioko_health
ln -sf /etc/nginx/sites-available/bioko_health /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
ok "Nginx configurado."

# ── Directorios y permisos ─────────────────────────────────────
mkdir -p /var/log/bioko_health /run/bioko_health \
         "$APP_DIR/uploads" "$APP_DIR/reports" \
         "$APP_DIR/logs" "$APP_DIR/flask_sessions"
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR" /var/log/bioko_health /run/bioko_health

# ── Systemd ────────────────────────────────────────────────────
cp "$APP_DIR/deploy/bioko_health.service" /etc/systemd/system/
systemctl daemon-reload && systemctl enable bioko_health && systemctl start bioko_health
ok "Servicio activo."

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  ✓ INSTALACIÓN SANITARIA lista                                   ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
printf "║  Instalación:  %-49s║\n" "$FACILITY_NAME"
printf "║  Tipo:         %-49s║\n" "$FACILITY_TYPE"
printf "║  Código:       %-49s║\n" "$FACILITY_CODE"
printf "║  IP local:     %-49s║\n" "$LAN_IP"
printf "║  Nodo prov.:   %-49s║\n" "$PROV_NODE_IP"
echo "║                                                                  ║"
echo "║  URL para tablets: http://$LAN_IP  o  http://salud.local        ║"
echo "║  Usuario: admin  |  Contraseña: Bioko2024!  ← CAMBIAR YA        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
