from flask import Blueprint, render_template, request, jsonify
from database_models import engine, Usuario, RolEnum
from sqlalchemy.orm import sessionmaker
from routes_auth import login_required, role_required

usuarios_bp = Blueprint('usuarios', __name__)
Session = sessionmaker(bind=engine)

@usuarios_bp.route('/usuarios', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def vista_usuarios():
    """
    Vista del panel de administración de usuarios.
    Permitido para Administrador y Gerencia.
    """
    session = Session()
    try:
        usuarios = session.query(Usuario).all()
        # Pasar los valores de RolEnum para el formulario de creación
        roles = [r.value for r in RolEnum]
        return render_template('usuarios.html', usuarios=usuarios, roles=roles)
    except Exception as e:
        return f"Error cargando gestión de usuarios: {e}", 500
    finally:
        session.close()

@usuarios_bp.route('/api/usuarios', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def crear_usuario():
    """
    Endpoint para registrar un nuevo usuario con hash de contraseña.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos"}), 400
        
    nombre = data.get('nombre')
    email = data.get('email')
    password = data.get('password')
    rol_str = data.get('rol')
    telefono = data.get('telefono', '')
    
    if not nombre or not email or not password or not rol_str:
        return jsonify({"error": "Faltan campos obligatorios"}), 400
        
    # Control de jerarquía: Gerencia solo puede crear usuarios con roles inferiores
    from flask import session as flask_session
    rol_actual = flask_session.get('usuario_rol')
    if rol_actual == RolEnum.GERENCIA.value:
        if rol_str in [RolEnum.ADMIN.value, RolEnum.GERENCIA.value]:
            return jsonify({"error": "No tienes permisos para crear usuarios con este rol"}), 403

    session = Session()
    try:
        # Verificar si el correo ya existe
        if session.query(Usuario).filter_by(email=email).first():
            return jsonify({"error": "El correo electrónico ya está registrado"}), 400
            
        # Convertir string de rol a Enum
        rol_enum = None
        for r in RolEnum:
            if r.value == rol_str:
                rol_enum = r
                break
                
        if not rol_enum:
            return jsonify({"error": "Rol no válido"}), 400
            
        nuevo_usuario = Usuario(
            nombre=nombre,
            email=email,
            rol=rol_enum,
            telefono=telefono
        )
        nuevo_usuario.set_password(password)
        
        session.add(nuevo_usuario)
        session.commit()
        
        return jsonify({"mensaje": "Usuario creado exitosamente"}), 201
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@usuarios_bp.route('/api/usuarios/<int:usuario_id>', methods=['PUT'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def editar_usuario(usuario_id):
    """
    Endpoint para editar la información de un usuario (Nombre, Email, Rol, Contraseña opcional).
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos"}), 400
        
    nombre = data.get('nombre')
    email = data.get('email')
    password = data.get('password')
    rol_str = data.get('rol')
    telefono = data.get('telefono', '')
    
    if not nombre or not email or not rol_str:
        return jsonify({"error": "Faltan campos obligatorios"}), 400
        
    session = Session()
    try:
        usuario = session.query(Usuario).filter_by(id=usuario_id).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
        # Control de jerarquía: Gerencia solo puede editar usuarios con roles inferiores
        from flask import session as flask_session
        rol_actual = flask_session.get('usuario_rol')
        if rol_actual == RolEnum.GERENCIA.value:
            if usuario.rol in [RolEnum.ADMIN, RolEnum.GERENCIA]:
                return jsonify({"error": "No tienes permisos para editar a este usuario"}), 403
            if rol_str in [RolEnum.ADMIN.value, RolEnum.GERENCIA.value]:
                return jsonify({"error": "No tienes permisos para asignar este rol"}), 403
            
        # Verificar duplicidad de email si cambió
        if usuario.email != email:
            if session.query(Usuario).filter_by(email=email).first():
                return jsonify({"error": "El correo electrónico ya está registrado por otro usuario"}), 400
                
        # Convertir string de rol a Enum
        rol_enum = None
        for r in RolEnum:
            if r.value == rol_str:
                rol_enum = r
                break
                
        if not rol_enum:
            return jsonify({"error": "Rol no válido"}), 400
            
        usuario.nombre = nombre
        usuario.email = email
        usuario.rol = rol_enum
        usuario.telefono = telefono
        
        if password and len(password.strip()) >= 6:
            usuario.set_password(password.strip())
            
        session.commit()
        return jsonify({"mensaje": "Usuario actualizado exitosamente"}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@usuarios_bp.route('/api/usuarios/<int:usuario_id>', methods=['DELETE'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def eliminar_usuario(usuario_id):
    """
    Endpoint para eliminar un usuario del sistema.
    """
    session = Session()
    try:
        usuario = session.query(Usuario).filter_by(id=usuario_id).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
        # Control de jerarquía: Gerencia solo puede eliminar usuarios con roles inferiores
        from flask import session as flask_session
        rol_actual = flask_session.get('usuario_rol')
        if rol_actual == RolEnum.GERENCIA.value:
            if usuario.rol in [RolEnum.ADMIN, RolEnum.GERENCIA]:
                return jsonify({"error": "No tienes permisos para eliminar a este usuario"}), 403
            
        # Opcional: Proteger para no auto-eliminarse
        from flask import session as flask_session
        if usuario.id == flask_session.get('usuario_id'):
            return jsonify({"error": "No puedes eliminar tu propia cuenta activa"}), 400
            
        session.delete(usuario)
        session.commit()
        return jsonify({"mensaje": "Usuario eliminado exitosamente"}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
