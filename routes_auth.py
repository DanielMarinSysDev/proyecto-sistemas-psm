from flask import Blueprint, request, jsonify, session
from functools import wraps
from database_models import engine, Usuario, RolEnum
from sqlalchemy.orm import sessionmaker

auth_bp = Blueprint('auth', __name__)
Session = sessionmaker(bind=engine)

def login_required(f):
    """
    Decorador para asegurar que un usuario ha iniciado sesión.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return jsonify({"error": "No has iniciado sesión. Acceso denegado."}), 401
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    """
    Decorador para proteger rutas según el rol del usuario.
    Toma una lista de roles permitidos (de RolEnum).
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Verificar si hay sesión activa
            if 'usuario_id' not in session:
                return jsonify({"error": "No has iniciado sesión. Acceso denegado."}), 401
            
            # 2. Verificar si el rol del usuario actual está en la lista de permitidos
            user_roles = session.get('usuario_roles', [])
            if not user_roles and session.get('usuario_rol'):
                user_roles = [session.get('usuario_rol')]
            
            # El Administrador siempre tiene acceso total
            if RolEnum.ADMIN.value in user_roles:
                return f(*args, **kwargs)
                
            # Verificar si alguno de los roles del usuario está permitido en esta ruta específica
            allowed_values = [rol.value for rol in allowed_roles]
            if not any(r in allowed_values for r in user_roles):
                return jsonify({"error": f"Acceso denegado. Se requiere uno de estos roles: {allowed_values}"}), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/api/login', methods=['POST'])
def login():
    """
    Endpoint para iniciar sesión en la Intranet.
    Espera JSON con: email, password.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos"}), 400
        
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Falta email o contraseña"}), 400
        
    db_session = Session()
    try:
        usuario = db_session.query(Usuario).filter_by(email=email).first()
        
        if not usuario or not usuario.check_password(password):
            return jsonify({"error": "Credenciales inválidas"}), 401
            
        # Guardar datos en la sesión (Cookie de Flask persistente)
        session.permanent = True
        session['usuario_id'] = usuario.id
        session['usuario_nombre'] = usuario.nombre
        session['usuario_rol'] = usuario.rol.value
        session['usuario_roles'] = [ur.rol.value for ur in usuario.roles]
        
        return jsonify({
            "mensaje": "Inicio de sesión exitoso",
            "usuario": {
                "id": usuario.id,
                "nombre": usuario.nombre,
                "rol": usuario.rol.value,
                "roles": [ur.rol.value for ur in usuario.roles]
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": "Error interno del servidor", "detalle": str(e)}), 500
    finally:
        db_session.close()

@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    """
    Endpoint para cerrar la sesión actual.
    """
    session.clear()
    return jsonify({"mensaje": "Sesión cerrada exitosamente"}), 200
