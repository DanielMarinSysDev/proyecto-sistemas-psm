from flask import Blueprint, request, jsonify, render_template
from database_models import engine, Cliente, RolEnum, LogAuditoria
from sqlalchemy.orm import sessionmaker
from file_manager import create_master_data_folder
import logging
from routes_auth import login_required, role_required

def normalizar_numero_db(numero: str) -> str:
    if not numero:
        return ""
    num_limpio = "".join(c for c in numero if c.isdigit())
    if num_limpio.startswith("0") and len(num_limpio) == 11:
        num_limpio = "58" + num_limpio[1:]
    elif (num_limpio.startswith("4") or num_limpio.startswith("2")) and len(num_limpio) == 10:
        num_limpio = "58" + num_limpio
    return f"+{num_limpio}"

logger = logging.getLogger(__name__)

clientes_bp = Blueprint('clientes', __name__)
Session = sessionmaker(bind=engine)

@clientes_bp.route('/api/clientes', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def crear_cliente():
    """
    Endpoint para registrar un nuevo cliente y generar su carpeta Master Data.
    Espera JSON con: nombre_empresa (obligatorio), contacto_nombre, email, telefono.
    """
    data = request.json
    
    if not data:
        return jsonify({"error": "No se enviaron datos"}), 400
        
    nombre_empresa = data.get('nombre_empresa')
    contacto_nombre = data.get('contacto_nombre', '')
    email = data.get('email', '')
    telefono = data.get('telefono', '')
    
    if not nombre_empresa:
        return jsonify({"error": "El campo 'nombre_empresa' es obligatorio"}), 400
        
    session = Session()
    try:
        # 1. Crear el cliente en la BD para obtener el ID autonumérico
        nuevo_cliente = Cliente(
            nombre_empresa=nombre_empresa,
            contacto_nombre=contacto_nombre,
            email=email,
            telefono=normalizar_numero_db(telefono)
        )
        session.add(nuevo_cliente)
        session.flush()  # Asigna el ID sin confirmar (commit) la transacción aún
        
        # 2. Generar carpeta Master Data físicamente en el servidor
        try:
            ruta_fisica = create_master_data_folder(nuevo_cliente.id, nombre_empresa)
            nuevo_cliente.ruta_activos_permanentes = ruta_fisica
        except Exception as file_e:
            logger.error(f"Error en creación de carpetas para cliente {nuevo_cliente.id}: {file_e}")
            session.rollback()
            return jsonify({"error": "No se pudieron crear las carpetas físicas en el servidor"}), 500
            
        # Registrar log de auditoría
        from flask import session as flask_session
        log_usuario_id = flask_session.get('usuario_id') or 1
        log = LogAuditoria(
            usuario_id=log_usuario_id,
            accion="CLIENTE CREACIÓN",
            detalles=f"Se creó el cliente '{nuevo_cliente.nombre_empresa}' (Contacto: {nuevo_cliente.contacto_nombre})"
        )
        session.add(log)
        
        # 3. Guardar todo si fue exitoso
        session.commit()
        
        return jsonify({
            "mensaje": "Cliente y Master Data creados exitosamente",
            "cliente_id": nuevo_cliente.id,
            "ruta_master_data": ruta_fisica
        }), 201
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error creando cliente: {e}")
        return jsonify({"error": "Error interno del servidor", "detalle": str(e)}), 500
    finally:
        session.close()

@clientes_bp.route('/api/clientes', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def obtener_clientes():
    """
    Endpoint para obtener la lista de clientes en formato JSON (usado para Selects).
    """
    session = Session()
    try:
        clientes = session.query(Cliente).all()
        return jsonify([
            {
                "id": c.id,
                "nombre_empresa": c.nombre_empresa,
                "contacto_nombre": c.contacto_nombre,
                "email": c.email,
                "telefono": c.telefono,
                "ruta_activos": c.ruta_activos_permanentes,
                "saldo_favor": c.saldo_favor or 0.0
            } for c in clientes
        ]), 200
    except Exception as e:
        logger.error(f"Error obteniendo clientes: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500
@clientes_bp.route('/api/clientes/<int:cliente_id>/expediente', methods=['GET'])
@login_required
def obtener_expediente_cliente(cliente_id):
    """
    Endpoint para obtener el Expediente Digital (Master Data) de un cliente:
    Historial de pedidos, órdenes de trabajo, diagnósticos e informes técnicos.
    """
    session = Session()
    try:
        from database_models import OrdenTrabajo, Pedido, Archivo
        cliente = session.query(Cliente).filter_by(id=cliente_id).first()
        if not cliente:
            return jsonify({"error": "Cliente no encontrado"}), 404
            
        ordenes = session.query(OrdenTrabajo).filter_by(cliente_id=cliente_id).order_by(OrdenTrabajo.fecha_creacion.desc()).all()
        
        historial_ordenes = []
        for o in ordenes:
            archivos = session.query(Archivo).filter_by(orden_id=o.id).all()
            historial_ordenes.append({
                "id": o.id,
                "pedido_id": o.pedido_id,
                "nombre_proyecto": o.nombre_proyecto,
                "estado": o.estado.value if hasattr(o.estado, 'value') else str(o.estado),
                "fecha_creacion": o.fecha_creacion.strftime('%Y-%m-%d %H:%M') if o.fecha_creacion else '',
                "precio": round(float(o.precio_proporcional or 0.0), 2),
                "abono": round(float(o.abono_proporcional or 0.0), 2),
                "saldo_pendiente": round(float(o.saldo_pendiente_proporcional or 0.0), 2),
                "tecnico": o.disenador.nombre if o.disenador else "Sin asignar",
                "diagnostico": {
                    "defectos": o.diagnostico_defectos or "",
                    "detalles": o.diagnostico_detalles or "",
                    "insumos": o.diagnostico_insumos or "",
                    "observaciones": o.diagnostico_observaciones or "",
                    "muestra": o.ruta_muestra or ""
                },
                "archivos": [
                    {
                        "id": a.id,
                        "nombre_original": a.nombre_original,
                        "tipo_categoria": a.tipo_categoria,
                        "fecha_subida": a.fecha_subida.strftime('%Y-%m-%d %H:%M') if a.fecha_subida else '',
                        "tipo": 'image' if any(a.nombre_original.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']) else ('pdf' if a.nombre_original.lower().endswith('.pdf') else 'other'),
                        "url_descarga": f"/api/ordenes/{o.id}/descargar-archivo/{a.nombre_original}",
                        "url_preview": f"/api/ordenes/{o.id}/preview/{a.nombre_original}"
                    } for a in archivos
                ]
            })
            
        return jsonify({
            "cliente": {
                "id": cliente.id,
                "nombre_empresa": cliente.nombre_empresa,
                "contacto_nombre": cliente.contacto_nombre,
                "email": cliente.email,
                "telefono": cliente.telefono,
                "saldo_favor": round(float(cliente.saldo_favor or 0.0), 2),
                "ruta_master_data": cliente.ruta_activos_permanentes or ""
            },
            "total_ordenes": len(historial_ordenes),
            "ordenes": historial_ordenes
        }), 200
    except Exception as e:
        logger.error(f"Error cargando expediente del cliente {cliente_id}: {e}")
        return jsonify({"error": "Error al cargar expediente"}), 500
    finally:
        session.close()

@clientes_bp.route('/clientes', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def vista_clientes():
    """
    Vista web para mostrar el directorio de clientes.
    """
    session = Session()
    try:
        clientes = session.query(Cliente).all()
        return render_template('clientes.html', clientes=clientes)
    except Exception as e:
        return f"Error cargando directorio de clientes: {e}", 500
    finally:
        session.close()

@clientes_bp.route('/api/clientes/<int:cliente_id>', methods=['DELETE'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def eliminar_cliente(cliente_id):
    """
    Elimina un cliente y todos sus pedidos/órdenes asociados gracias al cascade="all, delete-orphan".
    """
    session = Session()
    try:
        cliente = session.query(Cliente).filter_by(id=cliente_id).first()
        if not cliente:
            return jsonify({"error": "Cliente no encontrado"}), 404
            
        # Registrar log de auditoría
        from flask import session as flask_session
        log_usuario_id = flask_session.get('usuario_id') or 1
        log = LogAuditoria(
            usuario_id=log_usuario_id,
            accion="CLIENTE ELIMINACIÓN",
            detalles=f"Se eliminó el cliente '{cliente.nombre_empresa}' (ID: {cliente_id})"
        )
        session.add(log)
        session.delete(cliente)
        session.commit()
        
        return jsonify({"mensaje": f"Cliente '{cliente.nombre_empresa}' eliminado exitosamente"}), 200
    except Exception as e:
        session.rollback()
        logger.error(f"Error eliminando cliente {cliente_id}: {e}")
        return jsonify({"error": "Error interno al intentar eliminar"}), 500
    finally:
        session.close()

@clientes_bp.route('/api/clientes/<int:cliente_id>', methods=['PUT'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def editar_cliente(cliente_id):
    """
    Edita la información básica de un cliente existente.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos"}), 400
        
    nombre_empresa = data.get('nombre_empresa', '').strip()
    contacto_nombre = data.get('contacto_nombre', '').strip()
    email = data.get('email', '').strip()
    telefono = data.get('telefono', '').strip()
    
    if not nombre_empresa:
        return jsonify({"error": "El nombre de la empresa no puede estar vacío"}), 400
        
    session = Session()
    try:
        cliente = session.query(Cliente).filter_by(id=cliente_id).first()
        if not cliente:
            return jsonify({"error": "Cliente no encontrado"}), 404
            
        cliente.nombre_empresa = nombre_empresa
        cliente.contacto_nombre = contacto_nombre
        cliente.email = email
        cliente.telefono = normalizar_numero_db(telefono)
        
        # Registrar log de auditoría
        from flask import session as flask_session
        log_usuario_id = flask_session.get('usuario_id') or 1
        log = LogAuditoria(
            usuario_id=log_usuario_id,
            accion="CLIENTE MODIFICACIÓN",
            detalles=f"Se modificó el cliente '{cliente.nombre_empresa}' (Contacto: {cliente.contacto_nombre})"
        )
        session.add(log)
        session.commit()
        return jsonify({"mensaje": "Cliente actualizado exitosamente"}), 200
    except Exception as e:
        session.rollback()
        logger.error(f"Error actualizando cliente {cliente_id}: {e}")
        return jsonify({"error": "Error interno al intentar actualizar"}), 500
    finally:
        session.close()

import os

@clientes_bp.route('/api/abrir-carpeta', methods=['POST'])
@login_required
def abrir_carpeta():
    """
    Intenta abrir una carpeta local en el Explorador de Archivos de Windows.
    Solo funciona si el servidor de Flask y el usuario están en la misma máquina 
    o si la ruta es accesible por red para el servidor.
    """
    data = request.json
    ruta = data.get('ruta', '')
    
    if not ruta or not os.path.exists(ruta):
        return jsonify({"error": "La ruta no existe o es inválida"}), 400
        
    try:
        if os.name == 'nt': # Windows
            os.startfile(ruta)
        else:
            # Para Mac/Linux (por si acaso)
            import subprocess
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, ruta])
            
        return jsonify({"mensaje": "Carpeta abierta"}), 200
    except Exception as e:
        logger.error(f"Error abriendo carpeta {ruta}: {e}")
        return jsonify({"error": str(e)}), 500
