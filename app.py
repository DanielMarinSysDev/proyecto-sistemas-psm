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

@app.context_processor
def inject_global_vars():
    import os
    return {
        "usa_supabase": bool(os.environ.get('SUPABASE_URL'))
    }

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


# --- RUTA PÚBLICA PARA SEGUIMIENTO DE PEDIDOS POR EL CLIENTE ---
import hmac
import hashlib

def generar_token_pedido(pedido_id, secret_key):
    h = hmac.new(secret_key.encode('utf-8'), str(pedido_id).encode('utf-8'), hashlib.sha256)
    return h.hexdigest()[:16]

@app.route('/publico/pedido/<int:pedido_id>/<token>')
def ver_pedido_publico(pedido_id, token):
    # Verificar firma de seguridad
    expected_token = generar_token_pedido(pedido_id, app.config['SECRET_KEY'])
    if not hmac.compare_digest(expected_token, token):
        return render_template('public_error.html', mensaje="El enlace de seguimiento es inválido o ha expirado."), 403
        
    from database_models import engine, Pedido, Cliente, OrdenTrabajo, Configuracion
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        pedido = session.query(Pedido).filter_by(id=pedido_id).first()
        if not pedido:
            return render_template('public_error.html', mensaje="El pedido especificado no existe."), 404
            
        # Obtener coordenadas de pago globales
        cfg_zelle = session.query(Configuracion).filter_by(clave='pago_instrucciones_zelle').first()
        cfg_movil = session.query(Configuracion).filter_by(clave='pago_instrucciones_movil').first()
        cfg_trans = session.query(Configuracion).filter_by(clave='pago_instrucciones_transferencia').first()
        
        instrucciones = {
            'zelle': cfg_zelle.valor if cfg_zelle else 'Zelle: pagos@taskcore.com (TaskCore LLC)',
            'pago_movil': cfg_movil.valor if cfg_movil else 'Pago Móvil: Banesco (0134) - RIF: J-40012345-6 - Tel: 0424-1234567',
            'transferencia': cfg_trans.valor if cfg_trans else 'Transferencia: Banco Mercantil - Cta Corriente: 0105-0012-34-5678901234 - Beneficiario: TaskCore, C.A.'
        }
        
        return render_template('public_pedido.html', pedido=pedido, instrucciones=instrucciones)
    except Exception as e:
        return render_template('public_error.html', mensaje=f"Error interno del servidor: {e}"), 500
    finally:
        session.close()



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