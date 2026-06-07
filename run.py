"""
BIOKO HEALTH — Punto de entrada principal
"""
import os
from app import create_app

env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = env == 'development'
    print(f"""
╔══════════════════════════════════════════════╗
║         BIOKO HEALTH — Sistema de Salud       ║
║         República de Guinea Ecuatorial        ║
╠══════════════════════════════════════════════╣
║  Entorno  : {env:<34}║
║  Puerto   : {port:<34}║
║  URL      : http://localhost:{port:<18}║
╚══════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port, debug=debug)
