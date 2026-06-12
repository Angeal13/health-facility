"""
BIOKO HEALTH — Suite de Pruebas de Seguridad
=============================================
Valida los controles de seguridad críticos:
  1. CSRF activo en formularios
  2. Login funcional con token
  3. Open redirect bloqueado
  4. Redirect interno permitido
  5. Rate limiting contra fuerza bruta
  6. Control de roles (recepción no escribe consultas)
  7. Personal clínico sí accede
  8. Cabeceras de seguridad HTTP
  9. API de sync protegida por token HMAC

Ejecutar:  python -m pytest tests/ -v
       o:  python tests/test_seguridad.py
"""
import os
import re
import sys
import warnings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
warnings.filterwarnings('ignore')
os.environ.setdefault('SECRET_KEY', 'test-key-suite-seguridad')

from app import create_app
from app.models.models import db, Usuario
from app.extensions import limiter
from config import Config


class SecTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False
    RATELIMIT_STORAGE_URI = 'memory://'


def crear_app_prueba():
    import config as cfg
    cfg.config_by_name['sectest'] = SecTestConfig
    app = create_app('sectest')
    with app.app_context():
        db.create_all()
        for username, rol in [('dr.prueba', 'medico'), ('recepcion1', 'recepcion')]:
            u = Usuario(nombre_usuario=username, nombre_completo=username, rol=rol)
            u.set_password('password123')
            db.session.add(u)
        db.session.commit()
    return app


def get_token(client):
    resp = client.get('/auth/login')
    m = re.search(rb'name="csrf_token" value="([^"]+)"', resp.data)
    return m.group(1).decode() if m else ''


def do_login(client, user, pw):
    return client.post('/auth/login', data={
        'nombre_usuario': user, 'password': pw, 'csrf_token': get_token(client)
    }, follow_redirects=False)


def ejecutar_suite():
    app = crear_app_prueba()
    client = app.test_client()
    aprobadas = 0

    # 1 — CSRF
    assert client.post('/auth/login',
                       data={'nombre_usuario': 'x', 'password': 'y'}).status_code == 400
    aprobadas += 1
    print("✓ 1/9 CSRF rechaza POST sin token")

    # 2 — Login válido
    resp = do_login(client, 'dr.prueba', 'password123')
    assert resp.status_code == 302 and '/pacientes/dashboard' in resp.location
    aprobadas += 1
    print("✓ 2/9 Login válido funciona")
    client.get('/auth/logout')

    # 3 — Open redirect bloqueado
    token = get_token(client)
    resp = client.post('/auth/login?next=https://malicioso.com/x',
                       data={'nombre_usuario': 'dr.prueba', 'password': 'password123',
                             'csrf_token': token}, follow_redirects=False)
    assert 'malicioso' not in resp.location
    aprobadas += 1
    print("✓ 3/9 Open redirect bloqueado")
    client.get('/auth/logout')

    # 4 — Redirect interno permitido
    token = get_token(client)
    resp = client.post('/auth/login?next=/pacientes/',
                       data={'nombre_usuario': 'dr.prueba', 'password': 'password123',
                             'csrf_token': token}, follow_redirects=False)
    assert resp.location.endswith('/pacientes/')
    aprobadas += 1
    print("✓ 4/9 Redirect interno permitido")
    client.get('/auth/logout')

    limiter.reset()

    # 5 — Rate limiting
    codes = [do_login(client, 'atacante', f'x{i}').status_code for i in range(12)]
    assert 429 in codes, f"Rate limit no activo: {codes}"
    aprobadas += 1
    print(f"✓ 5/9 Rate limit activo (429 en intento #{codes.index(429)+1})")

    limiter.reset()

    # 6 — Recepción bloqueada
    c2 = app.test_client()
    do_login(c2, 'recepcion1', 'password123')
    assert c2.get('/consultas/nueva').status_code == 403
    aprobadas += 1
    print("✓ 6/9 Recepción bloqueada de crear consultas")

    # 7 — Médico permitido
    c3 = app.test_client()
    do_login(c3, 'dr.prueba', 'password123')
    assert c3.get('/consultas/nueva').status_code == 200
    aprobadas += 1
    print("✓ 7/9 Médico puede crear consultas")

    # 8 — Cabeceras
    resp = c3.get('/auth/login')
    assert resp.headers.get('X-Frame-Options') == 'DENY'
    assert resp.headers.get('X-Content-Type-Options') == 'nosniff'
    aprobadas += 1
    print("✓ 8/9 Cabeceras de seguridad presentes")

    # 9 — API sync
    assert app.test_client().get('/api/sync/estado').status_code == 401
    aprobadas += 1
    print("✓ 9/9 API sync protegida por token HMAC")

    print(f"\n{'='*44}\n  {aprobadas}/9 PRUEBAS DE SEGURIDAD APROBADAS\n{'='*44}")
    return aprobadas == 9


# Compatibilidad pytest
def test_suite_completa():
    assert ejecutar_suite()


if __name__ == '__main__':
    import logging
    logging.disable(logging.WARNING)
    ok = ejecutar_suite()
    sys.exit(0 if ok else 1)
