# Contribuir a Bioko Health

## Configurar el entorno de desarrollo

```bash
git clone https://github.com/TU_ORG/bioko-health.git
cd bioko-health

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.template .env
# FLASK_ENV=development ya está por defecto — usa SQLite

python scripts/seed_db.py
python run.py
```

## Ramas

| Rama | Propósito |
|------|-----------|
| `main` | Código estable — lo que está en producción |
| `develop` | Integración de features antes de pasar a main |
| `feature/xxx` | Nueva funcionalidad |
| `fix/xxx` | Corrección de errores |
| `deploy/xxx` | Cambios en scripts de despliegue |

## Convención de commits

```
feat(módulo): descripción corta
fix(módulo): descripción corta
docs: descripción
refactor(módulo): descripción
deploy(tipo-nodo): descripción
```

Ejemplos:
```
feat(pacientes): añadir búsqueda por grupo sanguíneo
fix(sync): corregir timeout en transferencia inter-provincial
deploy(instalacion): añadir configuración dnsmasq para tablets
```

## Antes de hacer un Pull Request

1. El código corre sin errores: `python run.py`
2. El seed funciona limpio: `python scripts/seed_db.py`
3. No hay secrets en el código (usar `.env`)
4. Los templates nuevos extienden `base.html`
5. Los formularios incluyen `{{ csrf_token() }}`
6. Las rutas nuevas están protegidas con `@login_required`

## Estructura de una ruta típica

```python
@blueprint.route('/ruta')
@login_required
def mi_vista():
    # Solo admins:
    if not current_user.es_admin:
        abort(403)
    # ...
    return render_template('modulo/vista.html', datos=datos)
```

## Variables de entorno sensibles

Nunca hardcodear en el código. Siempre usar `current_app.config.get('NOMBRE')` o `os.environ.get('NOMBRE')`.
El archivo `.env` nunca se commitea — está en `.gitignore`.
Los `.env.template` sí se commitean (sin valores reales).
