# ----------------------------------------------------------------------
# Copyright (c) 2026 Daniel Marin SysDev.
# Todos los derechos reservados.
# Este archivo es propiedad exclusiva de Daniel Marin.
# Queda prohibida su reproducción o distribución sin autorización.
# ----------------------------------------------------------------------
from flask import Blueprint, render_template, request, jsonify
from database_models import engine, Cliente, OrdenTrabajo
from sqlalchemy.orm import sessionmaker
from routes_auth import login_required, role_required
from database_models import engine, Cliente, OrdenTrabajo, RolEnum, EstadoOrdenEnum, Usuario, Pedido

dashboard_bp = Blueprint('dashboard', __name__)
Session = sessionmaker(bind=engine)

@dashboard_bp.route('/instalador', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.INSTALADOR)
def vista_instalador():
    """
    Vista móvil dedicada para Instaladores. Solo muestra trabajos listos para instalar.
    """
    session = Session()
    try:
        ordenes = session.query(OrdenTrabajo).join(Cliente).filter(
            OrdenTrabajo.estado == EstadoOrdenEnum.LISTO_INSTALAR_ENTREGAR
        ).all()
        return render_template('instalador.html', ordenes=ordenes)
    except Exception as e:
        return f"Error cargando app de instalador: {e}", 500
    finally:
        session.close()

@dashboard_bp.route('/ayuda', methods=['GET'])
@login_required
def vista_ayuda():
    """
    Renderiza la guía interactiva de uso del sistema.
    """
    return render_template('ayuda.html')

@dashboard_bp.route('/auditoria', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN)
def vista_auditoria():
    """
    Panel de visualización y filtrado de logs de auditoría para el Administrador.
    """
    session = Session()
    try:
        usuario_id_filter = request.args.get('usuario_id', type=int)
        fecha_filter = request.args.get('fecha', '').strip()
        query_filter = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = 50

        from database_models import LogAuditoria, Usuario
        from sqlalchemy import and_, or_, cast, Date
        from datetime import datetime
        import math

        # Query principal uniendo logs con el modelo de Usuario
        q = session.query(LogAuditoria, Usuario).outerjoin(Usuario, LogAuditoria.usuario_id == Usuario.id)

        filters = []
        if usuario_id_filter:
            filters.append(LogAuditoria.usuario_id == usuario_id_filter)

        if fecha_filter:
            try:
                f_date = datetime.strptime(fecha_filter, "%Y-%m-%d").date()
                filters.append(cast(LogAuditoria.fecha, Date) == f_date)
            except ValueError:
                pass

        if query_filter:
            busqueda = f"%{query_filter}%"
            filters.append(or_(
                LogAuditoria.accion.ilike(busqueda),
                LogAuditoria.detalles.ilike(busqueda)
            ))

        if filters:
            q = q.filter(and_(*filters))

        # Ordenar por fecha descendente
        q = q.order_by(LogAuditoria.fecha.desc())

        # Contar total para paginación
        total_logs = q.count()
        total_pages = math.ceil(total_logs / per_page) if total_logs > 0 else 1
        page = max(1, min(page, total_pages))

        # Obtener resultados paginados
        resultados = q.offset((page - 1) * per_page).limit(per_page).all()

        # Dar formato a los resultados
        logs_data = []
        for log, usr in resultados:
            logs_data.append({
                "id": log.id,
                "usuario_nombre": usr.nombre if usr else "Sistema (Automático)",
                "usuario_rol": usr.rol.value if usr else "Sistema",
                "orden_id": log.orden_id,
                "accion": log.accion,
                "detalles": log.detalles,
                "fecha": log.fecha.strftime("%Y-%m-%d %H:%M:%S")
            })

        # Listado de usuarios para el dropdown de filtros
        usuarios = session.query(Usuario).order_by(Usuario.nombre).all()
        usuarios_list = [{"id": u.id, "nombre": u.nombre} for u in usuarios]

        return render_template(
            'auditoria.html',
            logs=logs_data,
            usuarios=usuarios_list,
            current_usuario_id=usuario_id_filter,
            current_fecha=fecha_filter,
            current_query=query_filter,
            page=page,
            total_pages=total_pages,
            total_logs=total_logs
        )
    except Exception as e:
        return f"Error cargando panel de auditoría: {e}", 500
    finally:
        session.close()

@dashboard_bp.route('/dashboard')
@login_required
def vista_dashboard():
    """
    Renderiza la vista principal del Dashboard (Kanban)
    """
    session = Session()
    try:
        ordenes = session.query(OrdenTrabajo).join(Cliente).filter(
            OrdenTrabajo.estado.notin_([EstadoOrdenEnum.BORRADOR, EstadoOrdenEnum.CANCELADO])
        ).all()
        
        # Obtener diseñadores para el menú de asignación
        disenadores = session.query(Usuario).filter(Usuario.rol == RolEnum.DISENADOR).all()
        disenadores_data = [{"id": d.id, "nombre": d.nombre} for d in disenadores]
        
        # Convertir a diccionarios para Jinja/Alpine
        ordenes_data = []
        import datetime
        hoy = datetime.date.today()
        for o in ordenes:
            dias_transcurridos = (hoy - o.fecha_creacion.date()).days
            es_arrastrada = False
            dias_retraso = 0
            if o.estado != EstadoOrdenEnum.COMPLETADO and dias_transcurridos > 0:
                es_arrastrada = True
                dias_retraso = dias_transcurridos
                
            # Verificar si tiene incidencias activas
            incidencias_activas = [inc for inc in o.incidencias if inc.estado == "Pendiente"]
            tiene_incidencia = len(incidencias_activas) > 0
            detalle_incidencia = incidencias_activas[0].detalles if tiene_incidencia else ""
            tipo_incidencia = incidencias_activas[0].tipo_problema if tiene_incidencia else ""
            incidencia_id = incidencias_activas[0].id if tiene_incidencia else None

            # Calcular saldo pendiente
            saldo = 0.0
            ocultar_precio = False
            if o.pedido and o.pedido.ocultar_precio_ventas:
                from flask import session as flask_session
                usuario_rol = flask_session.get('usuario_rol')
                if usuario_rol in [RolEnum.VENTAS.value, RolEnum.DISENADOR.value, RolEnum.INSTALADOR.value]:
                    ocultar_precio = True

            if o.pedido and o.pedido.estado_pago != "Cancelado" and o.pedido.monto_total:
                total = o.pedido.monto_total
                if o.pedido.estado_pago == "Por Cancelar":
                    abono = 0.0
                else: # Es "Abono"
                    from routes_finanzas import extraer_monto_numerico
                    abono = extraer_monto_numerico(o.pedido.monto_abono)
                saldo = max(0.0, total - abono)
            
            monto_total_val = o.pedido.monto_total if o.pedido else 0.0
            if ocultar_precio:
                saldo = None
                monto_total_val = None
            
            ordenes_data.append({
                "id": o.id,
                "nombre_proyecto": o.nombre_proyecto,
                "cliente": o.cliente.nombre_empresa,
                "estado": o.estado.value,
                "fecha": o.fecha_creacion.strftime("%Y-%m-%d"),
                "ruta": o.ruta_archivos_transaccionales,
                "ruta_muestra": o.ruta_muestra,
                "ruta_instalacion": o.ruta_instalacion,
                "pedido_id": o.pedido_id,
                "disenador_id": o.disenador_id,
                "disenador_nombre": o.disenador.nombre if o.disenador else "Sin asignar",
                "es_arrastrada": es_arrastrada,
                "dias_retraso": dias_retraso,
                "tiene_incidencia": tiene_incidencia,
                "tipo_incidencia": tipo_incidencia,
                "detalle_incidencia": detalle_incidencia,
                "incidencia_id": incidencia_id,
                "saldo_pendiente": saldo,
                "monto_total": monto_total_val,
                "ocultar_precio": ocultar_precio,
                "requiere_cotizacion": o.requiere_cotizacion,
                "cliente_telefono": o.cliente.telefono if o.cliente else "",
                "cliente_contacto": o.cliente.contacto_nombre or o.cliente.nombre_empresa if o.cliente and (o.cliente.contacto_nombre or o.cliente.nombre_empresa) else "Cliente"
            })
            
        return render_template('dashboard.html', ordenes=ordenes_data, disenadores=disenadores_data)
    except Exception as e:
        return f"Error cargando dashboard: {e}", 500
    finally:
        session.close()

@dashboard_bp.route('/api/buscar', methods=['GET'])
@login_required
def buscar_ordenes():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
        
    session = Session()
    try:
        # Buscar por ID, Nombre de Proyecto o Nombre de Cliente
        busqueda = f"%{query}%"
        
        # Filtro: (OrdenTrabajo.id == query) OR (OrdenTrabajo.nombre_proyecto ILIKE) OR (Cliente.nombre_empresa ILIKE) OR (Pedido.referencia ILIKE)
        filtros = []
        if query.isdigit():
            filtros.append(OrdenTrabajo.id == int(query))
            
        filtros.append(OrdenTrabajo.nombre_proyecto.ilike(busqueda))
        filtros.append(Cliente.nombre_empresa.ilike(busqueda))
        filtros.append(Pedido.referencia.ilike(busqueda))
        
        from sqlalchemy import or_
        resultados = session.query(OrdenTrabajo).join(Cliente).outerjoin(Pedido).filter(or_(*filtros)).limit(10).all()
        
        data = []
        for o in resultados:
            ref_str = o.pedido.referencia if o.pedido else f"JOB-{o.id}"
            data.append({
                "id": o.id,
                "nombre_proyecto": o.nombre_proyecto,
                "cliente": o.cliente.nombre_empresa,
                "estado": o.estado.value,
                "fecha": o.fecha_creacion.strftime("%Y-%m-%d"),
                "ruta": o.ruta_archivos_transaccionales,
                "referencia": ref_str
            })
            
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

import os
import requests
import mimetypes
from werkzeug.utils import secure_filename
from database_models import LogAuditoria

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_supabase_storage(file_stream, filename, target_path, bucket_name="archivos", content_type=None):
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        return None
        
    supabase_url = supabase_url.rstrip("/")
    upload_url = f"{supabase_url}/storage/v1/object/{bucket_name}/{target_path}"
    
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "x-upsert": "true"
    }
    if content_type:
        headers["Content-Type"] = content_type
        
    file_stream.seek(0)
    file_data = file_stream.read()
    
    response = requests.post(upload_url, headers=headers, data=file_data)
    if response.status_code == 200:
        return f"{supabase_url}/storage/v1/object/public/{bucket_name}/{target_path}"
        
    put_response = requests.put(upload_url, headers=headers, data=file_data)
    if put_response.status_code == 200:
        return f"{supabase_url}/storage/v1/object/public/{bucket_name}/{target_path}"
        
    raise Exception(f"Fallo al subir a Supabase: {put_response.text}")

@dashboard_bp.route('/api/ordenes/<int:orden_id>/upload-<tipo>', methods=['POST'])
@login_required
def upload_archivo(orden_id, tipo):
    """
    Sube un archivo (muestra o instalacion) a la carpeta correspondiente de la orden.
    tipo debe ser 'muestra' o 'instalacion'.
    """
    if tipo not in ['muestra', 'instalacion']:
        return jsonify({"error": "Tipo de archivo inválido"}), 400
        
    if 'file' not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400
        
    if not allowed_file(file.filename):
        return jsonify({"error": "Formato no permitido (solo JPG, PNG, PDF)"}), 400
        
    session = Session()
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden or not orden.ruta_archivos_transaccionales:
            return jsonify({"error": "Orden no encontrada o sin carpeta asignada"}), 404
            
        filename = secure_filename(file.filename)
        
        # Determinar la subcarpeta
        folder_name = "Evidencia_Fotos"
        
        # Intentar subir a Supabase Storage si están las credenciales
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        
        if supabase_url and supabase_key:
            content_type, _ = mimetypes.guess_type(filename)
            target_path = f"orden_{orden.id}/{folder_name}/{filename}"
            try:
                file_path = upload_to_supabase_storage(file, filename, target_path, "archivos", content_type)
            except Exception as se:
                return jsonify({"error": f"Error subiendo a Supabase Storage: {se}"}), 500
        else:
            # Flujo local en disco
            target_dir = os.path.join(orden.ruta_archivos_transaccionales, folder_name)
            os.makedirs(target_dir, exist_ok=True)
            file_path = os.path.join(target_dir, filename)
            file.save(file_path)
        
        # Actualizar DB
        if tipo == 'muestra':
            orden.ruta_muestra = file_path
            accion = "Muestra Subida"
        else:
            orden.ruta_instalacion = file_path
            accion = "Prueba Instalación Subida"
            
        # Registrar Auditoría
        from flask import session as flask_session
        usuario_id = flask_session.get('usuario_id', 1)
        
        log = LogAuditoria(
            usuario_id=usuario_id,
            accion=accion,
            detalles=f"Archivo guardado en {folder_name}"
        )
        session.add(log)
        session.commit()
        
        return jsonify({
            "mensaje": f"Archivo de {tipo} subido exitosamente",
            "ruta": file_path
        }), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dashboard_bp.route('/api/ordenes/<int:orden_id>/descargar/<tipo>', methods=['GET'])
@login_required
def descargar_archivo_orden(orden_id, tipo):
    """
    Descarga o redirecciona al archivo (muestra o instalacion) de la orden.
    tipo debe ser 'muestra' o 'instalacion'.
    """
    if tipo not in ['muestra', 'instalacion']:
        return jsonify({"error": "Tipo de archivo inválido"}), 400
        
    session = Session()
    try:
        orden = session.query(OrdenTrabajo).filter(OrdenTrabajo.id == orden_id).first()
        if not orden:
            return jsonify({"error": "Orden no encontrada"}), 404
            
        file_path = orden.ruta_muestra if tipo == 'muestra' else orden.ruta_instalacion
        if not file_path:
            return jsonify({"error": "No hay ningún archivo cargado para este tipo en la orden"}), 404
            
        # Si es una URL (Supabase/Nube)
        if file_path.startswith("http://") or file_path.startswith("https://"):
            from flask import redirect
            return redirect(file_path)
            
        # Si es un archivo local en disco
        if not os.path.exists(file_path):
            return jsonify({"error": "El archivo físico no existe en el servidor local"}), 404
            
        from flask import send_from_directory
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        return send_from_directory(directory, filename, as_attachment=True)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dashboard_bp.route('/api/ordenes/<int:orden_id>/archivos', methods=['GET'])
@login_required
def listar_archivos_orden(orden_id):
    """
    Lista todos los archivos subidos en la carpeta Evidencia_Fotos de la orden,
    tanto de forma local como en Supabase Storage.
    """
    session = Session()
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden:
            return jsonify({"error": "Orden no encontrada"}), 404
            
        archivos = []
        
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        
        def format_size(size_bytes):
            if size_bytes >= 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.2f} MB"
            elif size_bytes >= 1024:
                return f"{size_bytes / 1024:.2f} KB"
            return f"{size_bytes} B"

        def is_image_file(fname):
            ext = fname.split('.')[-1].lower() if '.' in fname else ''
            return ext in ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp']

        if supabase_url and supabase_key:
            import requests
            bucket_name = "archivos"
            prefix = f"orden_{orden.id}/Evidencia_Fotos"
            
            list_url = f"{supabase_url.rstrip('/')}/storage/v1/object/list/{bucket_name}"
            headers = {
                "Authorization": f"Bearer {supabase_key}",
                "apikey": supabase_key,
                "Content-Type": "application/json"
            }
            payload = {
                "prefix": prefix,
                "options": {
                    "limit": 100,
                    "offset": 0,
                    "sortBy": {
                        "column": "name",
                        "order": "asc"
                    }
                }
            }
            
            response = requests.post(list_url, headers=headers, json=payload)
            if response.status_code == 200:
                objects = response.json()
                for obj in objects:
                    name = obj.get('name')
                    if not name or name == '.placeholder':
                        continue
                    
                    size_bytes = obj.get('metadata', {}).get('size', 0)
                    tamanio = format_size(size_bytes)
                    tipo = 'image' if is_image_file(name) else ('pdf' if name.lower().endswith('.pdf') else 'other')
                    
                    url_descarga = f"{supabase_url.rstrip('/')}/storage/v1/object/public/{bucket_name}/{prefix}/{name}"
                    url_preview = f"/api/ordenes/{orden.id}/preview/{name}"
                    
                    archivos.append({
                        "nombre": name,
                        "tamanio": tamanio,
                        "tipo": tipo,
                        "url_descarga": url_descarga,
                        "url_preview": url_preview
                    })
        else:
            if orden.ruta_archivos_transaccionales:
                local_dir = os.path.join(orden.ruta_archivos_transaccionales, "Evidencia_Fotos")
                if os.path.exists(local_dir):
                    for filename in os.listdir(local_dir):
                        file_path = os.path.join(local_dir, filename)
                        if os.path.isfile(file_path):
                            size_bytes = os.path.getsize(file_path)
                            tamanio = format_size(size_bytes)
                            tipo = 'image' if is_image_file(filename) else ('pdf' if filename.lower().endswith('.pdf') else 'other')
                            
                            url_descarga = f"/api/ordenes/{orden.id}/descargar-archivo/{filename}"
                            url_preview = f"/api/ordenes/{orden.id}/preview/{filename}"
                            
                            archivos.append({
                                "nombre": filename,
                                "tamanio": tamanio,
                                "tipo": tipo,
                                "url_descarga": url_descarga,
                                "url_preview": url_preview
                            })
                            
        return jsonify({"archivos": archivos}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dashboard_bp.route('/api/ordenes/<int:orden_id>/descargar-archivo/<filename>', methods=['GET'])
@login_required
def descargar_archivo_especifico(orden_id, filename):
    """
    Descarga un archivo específico local de la orden.
    """
    session = Session()
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden or not orden.ruta_archivos_transaccionales:
            return jsonify({"error": "Orden no encontrada"}), 404
            
        file_path = os.path.join(orden.ruta_archivos_transaccionales, "Evidencia_Fotos", filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "El archivo físico no existe"}), 404
            
        from flask import send_from_directory
        return send_from_directory(os.path.dirname(file_path), filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dashboard_bp.route('/api/ordenes/<int:orden_id>/preview/<filename>', methods=['GET'])
@login_required
def previsualizar_archivo(orden_id, filename):
    """
    Genera y sirve una previsualización (thumbnail) optimizada del archivo.
    Utiliza almacenamiento en caché en el servidor para evitar sobrecargar la CPU.
    """
    session = Session()
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden:
            return jsonify({"error": "Orden no encontrada"}), 404
            
        def is_image_file(fname):
            ext = fname.split('.')[-1].lower() if '.' in fname else ''
            return ext in ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp']

        # Determinar si es imagen
        if not is_image_file(filename):
            return jsonify({"error": "Solo se generan previsualizaciones para archivos de imagen"}), 400

        # Ruta del Cache en el servidor
        from file_manager import BASE_DIR
        cache_dir = os.path.join(BASE_DIR, "Cache_Previews")
        os.makedirs(cache_dir, exist_ok=True)
        cache_filename = f"orden_{orden.id}_{filename}_300x300.jpg"
        cache_path = os.path.join(cache_dir, cache_filename)

        # Si ya existe en caché, servirlo directamente con headers de cache fuertes
        from flask import send_file, make_response
        import mimetypes
        if os.path.exists(cache_path):
            response = make_response(send_file(cache_path, mimetype='image/jpeg'))
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            return response

        # Obtener los bytes originales de la imagen
        file_bytes = None
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        
        if supabase_url and supabase_key:
            import requests
            file_url = f"{supabase_url.rstrip('/')}/storage/v1/object/public/archivos/orden_{orden.id}/Evidencia_Fotos/{filename}"
            res = requests.get(file_url)
            if res.status_code == 200:
                file_bytes = res.content
        else:
            if orden.ruta_archivos_transaccionales:
                local_path = os.path.join(orden.ruta_archivos_transaccionales, "Evidencia_Fotos", filename)
                if os.path.exists(local_path):
                    with open(local_path, "rb") as f:
                        file_bytes = f.read()

        if not file_bytes:
            return jsonify({"error": "Archivo original no encontrado"}), 404

        # Intentar redimensionar con Pillow
        import io
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes))
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            img.thumbnail((300, 300))
            
            img.save(cache_path, format="JPEG", quality=70)
            
            response = make_response(send_file(cache_path, mimetype='image/jpeg'))
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            return response
        except Exception as pe:
            response = make_response(file_bytes)
            content_type, _ = mimetypes.guess_type(filename)
            response.headers['Content-Type'] = content_type or 'image/jpeg'
            response.headers['Cache-Control'] = 'public, max-age=3600'
            return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dashboard_bp.route('/api/ordenes/<int:orden_id>/asignar', methods=['PUT'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def asignar_disenador(orden_id):
    """
    Endpoint para asignar un diseñador a una orden de trabajo.
    Espera JSON: { disenador_id: int }
    """
    data = request.json
    disenador_id = data.get('disenador_id')
    
    if not disenador_id:
        return jsonify({"error": "Falta el ID del diseñador"}), 400
        
    session = Session()
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden:
            return jsonify({"error": "Orden no encontrada"}), 404
            
        disenador = session.query(Usuario).filter_by(id=disenador_id).first()
        if not disenador or disenador.rol != RolEnum.DISENADOR:
            return jsonify({"error": "Usuario inválido o no es diseñador"}), 400
            
        orden.disenador_id = disenador.id
        
        # Registrar Auditoría
        from flask import session as flask_session
        usuario_id = flask_session.get('usuario_id', 1)
        log = LogAuditoria(
            usuario_id=usuario_id,
            orden_id=orden.id,
            accion="Asignación",
            detalles=f"Se asignó el diseñador {disenador.nombre} al artículo"
        )
        session.add(log)
        session.commit()
        
        return jsonify({
            "mensaje": f"Asignado a {disenador.nombre}",
            "disenador_nombre": disenador.nombre
        }), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@dashboard_bp.route('/admin/mantenimiento', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN)
def vista_mantenimiento():
    """
    Renderiza la vista de mantenimiento y respaldos de base de datos.
    """
    import os
    from datetime import datetime
    carpeta_respaldos = os.getenv("BACKUP_DIR")
    if not carpeta_respaldos:
        ruta_raiz = os.path.dirname(os.path.abspath(__file__))
        carpeta_respaldos = os.path.join(ruta_raiz, "respaldos")

    archivos = []
    if os.path.exists(carpeta_respaldos):
        archivos = [f for f in os.listdir(carpeta_respaldos) if f.endswith(".sql")]
        archivos.sort(key=lambda x: os.path.getmtime(os.path.join(carpeta_respaldos, x)), reverse=True)

    respaldos_info = []
    for f in archivos:
        ruta_completa = os.path.join(carpeta_respaldos, f)
        stat = os.stat(ruta_completa)
        tamano_kb = stat.st_size / 1024
        fecha_mod = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        respaldos_info.append({
            "nombre": f,
            "tamano": f"{tamano_kb:.1f} KB",
            "fecha": fecha_mod
        })

    return render_template('mantenimiento.html', respaldos=respaldos_info)

@dashboard_bp.route('/api/mantenimiento/respaldar', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN)
def api_respaldar():
    import os
    from respaldar_db import realizar_respaldo
    from database_models import LogAuditoria
    exito, msg = realizar_respaldo()
    if exito:
        from flask import session as flask_session
        session_db = Session()
        try:
            log = LogAuditoria(
                usuario_id=flask_session.get('usuario_id', 1),
                accion="Respaldo Manual",
                detalles=f"Respaldo creado: {os.path.basename(msg)}"
            )
            session_db.add(log)
            session_db.commit()
        except Exception:
            session_db.rollback()
        finally:
            session_db.close()
        return jsonify({"mensaje": f"Respaldo creado exitosamente: {os.path.basename(msg)}"}), 200
    else:
        return jsonify({"error": f"Fallo al crear respaldo: {msg}"}), 500

@dashboard_bp.route('/api/mantenimiento/restaurar', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN)
def api_restaurar():
    import os
    data = request.json or {}
    filename = data.get('filename')
    password = data.get('password')
    if not filename:
        return jsonify({"error": "Debe especificar el nombre del archivo de respaldo"}), 400
    if not password:
        return jsonify({"error": "Se requiere la contraseña de administrador para proceder."}), 401

    filename = os.path.basename(filename)

    # Validar credenciales
    db_session = Session()
    try:
        from flask import session as flask_session
        usuario_id = flask_session.get('usuario_id')
        usuario = db_session.query(Usuario).filter_by(id=usuario_id).first()
        if not usuario or not usuario.check_password(password):
            return jsonify({"error": "Contraseña incorrecta. Acción cancelada."}), 401
    finally:
        db_session.close()

    from restaurar_db import restaurar_archivo
    from database_models import LogAuditoria
    exito, msg = restaurar_archivo(filename)
    if exito:
        session_db = Session()
        try:
            log = LogAuditoria(
                usuario_id=usuario_id,
                accion="Restauración Manual",
                detalles=f"Base de datos restaurada usando respaldo: {filename}"
            )
            session_db.add(log)
            session_db.commit()
        except Exception:
            session_db.rollback()
        finally:
            session_db.close()
        return jsonify({"mensaje": "Base de datos restaurada exitosamente."}), 200
    else:
        return jsonify({"error": f"Fallo al restaurar la base de datos: {msg}"}), 500

@dashboard_bp.route('/api/mantenimiento/respaldos/<filename>/descargar', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN)
def descargar_respaldo(filename):
    import os
    data = request.json or {}
    password = data.get('password')
    if not password:
        return jsonify({"error": "Se requiere la contraseña de administrador para descargar el respaldo."}), 401

    # Validar credenciales
    db_session = Session()
    try:
        from flask import session as flask_session
        usuario_id = flask_session.get('usuario_id')
        usuario = db_session.query(Usuario).filter_by(id=usuario_id).first()
        if not usuario or not usuario.check_password(password):
            return jsonify({"error": "Contraseña incorrecta. Acción cancelada."}), 401
    finally:
        db_session.close()

    carpeta_respaldos = os.getenv("BACKUP_DIR")
    if not carpeta_respaldos:
        ruta_raiz = os.path.dirname(os.path.abspath(__file__))
        carpeta_respaldos = os.path.join(ruta_raiz, "respaldos")

    filename = os.path.basename(filename)
    filepath = os.path.join(carpeta_respaldos, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "El archivo de respaldo no existe."}), 404

    # Registrar auditoría
    db_session = Session()
    try:
        from database_models import LogAuditoria
        log = LogAuditoria(
            usuario_id=usuario_id,
            accion="Descarga de Respaldo",
            detalles=f"Se descargó el archivo de respaldo: {filename}"
        )
        db_session.add(log)
        db_session.commit()
    except Exception:
        db_session.rollback()
    finally:
        db_session.close()

    from flask import send_from_directory
    return send_from_directory(carpeta_respaldos, filename, as_attachment=True)

@dashboard_bp.route('/api/mantenimiento/subir-restaurar', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN)
def api_subir_restaurar():
    import os
    from datetime import datetime
    from werkzeug.utils import secure_filename

    password = request.form.get('password')
    if not password:
        return jsonify({"error": "Se requiere la contraseña de administrador para restaurar un respaldo."}), 401

    # Validar credenciales
    db_session = Session()
    try:
        from flask import session as flask_session
        usuario_id = flask_session.get('usuario_id')
        usuario = db_session.query(Usuario).filter_by(id=usuario_id).first()
        if not usuario or not usuario.check_password(password):
            return jsonify({"error": "Contraseña incorrecta. Acción cancelada."}), 401
    finally:
        db_session.close()

    if 'file' not in request.files:
        return jsonify({"error": "No se subió ningún archivo."}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nombre de archivo vacío."}), 400

    if not file.filename.endswith('.sql'):
        return jsonify({"error": "Solo se permiten archivos de respaldo con extensión .sql."}), 400

    carpeta_respaldos = os.getenv("BACKUP_DIR")
    if not carpeta_respaldos:
        ruta_raiz = os.path.dirname(os.path.abspath(__file__))
        carpeta_respaldos = os.path.join(ruta_raiz, "respaldos")

    if not os.path.exists(carpeta_respaldos):
        os.makedirs(carpeta_respaldos)

    fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = secure_filename(file.filename)
    filename = f"respaldo_subido_{fecha_str}_{safe_name}"
    filepath = os.path.abspath(os.path.join(carpeta_respaldos, filename))

    try:
        file.save(filepath)

        # Validaciones de integridad del archivo
        if os.path.getsize(filepath) == 0:
            os.remove(filepath)
            return jsonify({"error": "El archivo de respaldo subido está vacío."}), 400

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(1000)
            if not ("PostgreSQL database dump" in head or "CREATE TABLE" in head or "INSERT INTO" in head or "--" in head):
                os.remove(filepath)
                return jsonify({"error": "El archivo no parece ser un respaldo SQL válido."}), 400

        # Ejecutar la restauración
        from restaurar_db import restaurar_archivo
        from database_models import LogAuditoria
        
        exito, msg = restaurar_archivo(filepath)
        if exito:
            session_db = Session()
            try:
                log = LogAuditoria(
                    usuario_id=usuario_id,
                    accion="Restauración por Carga",
                    detalles=f"Base de datos restaurada mediante archivo subido: {safe_name}"
                )
                session_db.add(log)
                session_db.commit()
            except Exception:
                session_db.rollback()
            finally:
                session_db.close()
            return jsonify({"mensaje": "Base de datos restaurada exitosamente desde el archivo cargado."}), 200
        else:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"error": f"Fallo al restaurar la base de datos: {msg}"}), 500

    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": f"Error al procesar el archivo: {str(e)}"}), 500

@dashboard_bp.route('/api/admin/system/update', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN)
def api_actualizar_sistema():
    """
    Actualiza el sistema desde el repositorio de Git remoto y recarga los procesos.
    """
    import subprocess
    import os
    try:
        # Ejecutar git pull para actualizar el código
        resultado_git = subprocess.run(
            ["git", "pull"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            check=True
        )
        # Opcional: instalar nuevas dependencias
        subprocess.run(
            ["pip", "install", "-r", "requirements.txt"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True
        )
        return jsonify({
            "mensaje": "Actualización de Git exitosa. Reiniciando servidor...",
            "salida": resultado_git.stdout
        }), 200
    except Exception as e:
        return jsonify({"error": f"Fallo al ejecutar la actualización: {str(e)}"}), 500
