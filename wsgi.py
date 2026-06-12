"""
BIOKO HEALTH — Punto de entrada WSGI para producción
=====================================================
Usado por gunicorn:
    gunicorn -c deploy/gunicorn.conf.py wsgi:app
"""
import os
from app import create_app

app = create_app(os.environ.get('FLASK_ENV', 'production'))
