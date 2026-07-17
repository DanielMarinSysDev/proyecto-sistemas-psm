# ----------------------------------------------------------------------
# Copyright (c) 2026 Daniel Marin SysDev.
# Todos los derechos reservados.
# Este archivo es propiedad exclusiva de Daniel Marin.
# Queda prohibida su reproducción o distribución sin autorización.
# ----------------------------------------------------------------------
from flask import Flask, render_template, redirect, request
import os
from dotenv import load_dotenv
load_dotenv()

# Inicializar base de datos y parches de esquema (omitir en pruebas para evitar bloqueos de archivo SQLite)
if os.getenv("TESTING") != "true":
    from database_models import init_db
    try:
        init_db()
    except Exception as e:
        print(f"Error al inicializar base de datos en app.py: {e}")

# Importar las rutas (Blueprints) de TaskCore
from routes_recepcion import recepcion_bp
from routes_clientes import clientes_bp
from routes_auth import auth_bp
from routes_dashboard import dashboard_bp
from routes_usuarios import usuarios_bp
from routes_finanzas import finanzas_bp
from routes_precios import precios_bp

from datetime import timedelta

app = Flask(__name__)

# Configuración básica
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev_key_temporal_secreta_12345")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Registrar blueprints
app.register_blueprint(recepcion_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(finanzas_bp)
app.register_blueprint(precios_bp)

# Ruta base
@app.route('/')
def index():
    return redirect('/login')

@app.route('/login')
def vista_login():
    return render_template('login.html')

@app.route('/health')
def health_check():
    """
    Ruta pública simple para mantener activo el servicio en Render (Keep-Alive)
    y para monitorear el estado básico de la aplicación.
    """
    return {"status": "healthy", "service": "TaskCore"}, 200


if __name__ == '__main__':
    # Asegurar e inicializar estructura de carpetas
    try:
        from file_manager import inicializar_carpetas_sistema
        inicializar_carpetas_sistema()
    except Exception as e:
        print(f"Error al inicializar carpetas del sistema: {e}")

    # El host '0.0.0.0' es VITAL para que las otras PCs y tu teléfono puedan entrar
    app.run(host='0.0.0.0', port=80, debug=True)

    # Trigger hot reload