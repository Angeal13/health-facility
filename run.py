"""
BIOKO HEALTH — Punto de entrada para desarrollo
================================================
Uso (solo desarrollo):
    python run.py

Para producción usar gunicorn (ver deploy/gunicorn.service):
    gunicorn -c deploy/gunicorn.conf.py wsgi:app
"""
import os
from app import create_app

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(
        host=app.config.get('LAN_HOST', '0.0.0.0'),
        port=app.config.get('LAN_PORT', 5000),
        debug=app.config.get('DEBUG', False),
    )
