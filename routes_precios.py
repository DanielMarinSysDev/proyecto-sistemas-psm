import math
from flask import Blueprint, render_template, request, jsonify, session as flask_session
from database_models import engine, PrecioMaterial, RolEnum, LogAuditoria, Configuracion
from sqlalchemy.orm import sessionmaker
from routes_auth import login_required, role_required

precios_bp = Blueprint('precios', __name__)
Session = sessionmaker(bind=engine)

@precios_bp.route('/precios', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def vista_precios():
    """
    Vista de administración de precios y tarifas de materiales.
    Exclusivo para Administrador.
    """
    session = Session()
    try:
        precios = session.query(PrecioMaterial).order_by(PrecioMaterial.tipo_trabajo, PrecioMaterial.material).all()
        # Obtener tipos de trabajo únicos y materiales
        tipos_trabajo = ["Computadora / Laptop", "Celular / Smartphone", "Tablet", "Servidor / Redes", "Consola de Videojuegos", "Otro"]
        return render_template('precios.html', precios=precios, tipos_trabajo=tipos_trabajo)
    except Exception as e:
        return f"Error cargando administración de precios: {e}", 500
    finally:
        session.close()

@precios_bp.route('/api/precios', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def guardar_precio():
    """
    Endpoint para crear o actualizar un precio de material o acabado/adicional.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos"}), 400
        
    precio_id = data.get('id')
    tipo_trabajo = data.get('tipo_trabajo')
    material = data.get('material')
    precio_m2 = float(data.get('precio_m2', 0.0))
    es_adicional = bool(data.get('es_adicional', False))
    
    if not tipo_trabajo or not material:
        return jsonify({"error": "Faltan campos obligatorios"}), 400
        
    session = Session()
    try:
        usuario_id = flask_session.get('usuario_id')
        if precio_id:
            # Actualización
            precio_entry = session.query(PrecioMaterial).filter_by(id=precio_id).first()
            if not precio_entry:
                return jsonify({"error": "Precio no encontrado"}), 404
                
            detalles_log = f"Precio modificado para {tipo_trabajo} - {material} ({'Adicional' if es_adicional else 'Base'}): ${precio_entry.precio_m2} -> ${precio_m2}"
            
            precio_entry.tipo_trabajo = tipo_trabajo
            precio_entry.material = material
            precio_entry.precio_m2 = precio_m2
            precio_entry.precio_laminado_m2 = 0.0
            precio_entry.es_adicional = es_adicional
            accion_log = "Precio Actualizado"
        else:
            # Creación
            # Verificar si ya existe para evitar duplicados
            existente = session.query(PrecioMaterial).filter_by(
                tipo_trabajo=tipo_trabajo, 
                material=material,
                es_adicional=es_adicional
            ).first()
            if existente:
                return jsonify({"error": f"Ya existe una tarifa para {tipo_trabajo} - {material}"}), 400
                
            precio_entry = PrecioMaterial(
                tipo_trabajo=tipo_trabajo,
                material=material,
                precio_m2=precio_m2,
                precio_laminado_m2=0.0,
                es_adicional=es_adicional
            )
            session.add(precio_entry)
            detalles_log = f"Nueva tarifa agregada para {tipo_trabajo} - {material} ({'Adicional' if es_adicional else 'Base'}): ${precio_m2}/m2"
            accion_log = "Precio Creado"
            
        # Registrar auditoría
        log = LogAuditoria(
            usuario_id=usuario_id,
            accion=accion_log,
            detalles=detalles_log
        )
        session.add(log)
        session.commit()
        return jsonify({"mensaje": "Tarifa guardada exitosamente"}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@precios_bp.route('/api/precios/<int:precio_id>', methods=['DELETE'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def eliminar_precio(precio_id):
    """
    Endpoint para eliminar una tarifa de material.
    """
    session = Session()
    try:
        precio_entry = session.query(PrecioMaterial).filter_by(id=precio_id).first()
        if not precio_entry:
            return jsonify({"error": "Tarifa no encontrada"}), 404
            
        usuario_id = flask_session.get('usuario_id')
        detalles_log = f"Tarifa eliminada para {precio_entry.tipo_trabajo} - {precio_entry.material}"
        
        session.delete(precio_entry)
        
        # Registrar auditoría
        log = LogAuditoria(
            usuario_id=usuario_id,
            accion="Precio Eliminado",
            detalles=detalles_log
        )
        session.add(log)
        session.commit()
        return jsonify({"mensaje": "Tarifa eliminada exitosamente"}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@precios_bp.route('/api/precios/listar', methods=['GET'])
@login_required
def listar_precios_api():
    """
    Retorna la lista de todas las tarifas de materiales configuradas en el sistema.
    """
    session = Session()
    try:
        precios = session.query(PrecioMaterial).order_by(PrecioMaterial.tipo_trabajo, PrecioMaterial.material).all()
        lista = []
        for p in precios:
            lista.append({
                "id": p.id,
                "tipo_trabajo": p.tipo_trabajo,
                "material": p.material,
                "precio_m2": p.precio_m2,
                "precio_laminado_m2": 0.0,
                "es_adicional": p.es_adicional
            })
        return jsonify(lista), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@precios_bp.route('/api/configuracion/redondeo', methods=['GET', 'POST'])
@login_required
def configuracion_redondeo():
    """
    Obtiene o actualiza la política de redondeo global de precios.
    """
    session = Session()
    try:
        if request.method == 'POST':
            # Solo Administrador puede guardar configuración
            usuario_rol = flask_session.get('usuario_rol')
            if usuario_rol != RolEnum.ADMIN.value:
                return jsonify({"error": "No autorizado"}), 403
                
            data = request.json or {}
            valor = data.get('valor')
            if valor not in ['exacto', 'entero_superior', 'decimal_cercano']:
                return jsonify({"error": "Valor de redondeo no válido"}), 400
                
            config = session.query(Configuracion).filter_by(clave='tipo_redondeo').first()
            valor_previo = config.valor if config else '(no definido)'
            if not config:
                config = Configuracion(clave='tipo_redondeo', valor=valor)
                session.add(config)
            else:
                config.valor = valor
                
            log = LogAuditoria(
                usuario_id=flask_session.get('usuario_id'),
                accion="Configuración Modificada",
                detalles=f"Redondeo global modificado: '{valor_previo}' -> '{valor}'"
            )
            session.add(log)
            session.commit()
            return jsonify({"mensaje": "Configuración de redondeo actualizada", "valor": valor}), 200
            
        else: # GET
            config = session.query(Configuracion).filter_by(clave='tipo_redondeo').first()
            valor = config.valor if config else 'exacto'
            return jsonify({"valor": valor}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@precios_bp.route('/api/configuracion/intervalo_recordatorio', methods=['GET', 'POST'])
@login_required
def configuracion_intervalo_recordatorio():
    """
    Obtiene o actualiza el intervalo (en días) para recordatorios de pago.
    """
    session = Session()
    try:
        from flask import session as flask_session
        if request.method == 'POST':
            # Solo Administrador y Gerencia pueden guardar configuración
            usuario_rol = flask_session.get('usuario_rol')
            if usuario_rol not in [RolEnum.ADMIN.value, RolEnum.GERENCIA.value]:
                return jsonify({"error": "No autorizado"}), 403
                
            data = request.json or {}
            valor = str(data.get('valor', '3'))
            if not valor.isdigit() or int(valor) <= 0:
                return jsonify({"error": "Intervalo no válido"}), 400
                
            config = session.query(Configuracion).filter_by(clave='intervalo_recordatorio_dias').first()
            valor_previo = config.valor if config else '(no definido)'
            if not config:
                config = Configuracion(clave='intervalo_recordatorio_dias', valor=valor)
                session.add(config)
            else:
                config.valor = valor
                
            log = LogAuditoria(
                usuario_id=flask_session.get('usuario_id'),
                accion="Configuración Modificada",
                detalles=f"Intervalo recordatorio deudas modificado: '{valor_previo}' -> '{valor}' días"
            )
            session.add(log)
            session.commit()
            return jsonify({"mensaje": "Configuración de intervalo de recordatorio actualizada", "valor": valor}), 200
            
        else: # GET
            config = session.query(Configuracion).filter_by(clave='intervalo_recordatorio_dias').first()
            valor = config.valor if config else '3'
            return jsonify({"valor": valor}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@precios_bp.route('/api/configuracion/precio_minimo', methods=['GET', 'POST'])
@login_required
def configuracion_precio_minimo():
    """
    Obtiene o actualiza el precio mínimo por artículo/item.
    """
    session = Session()
    try:
        from flask import session as flask_session
        if request.method == 'POST':
            # Solo Administrador puede guardar
            usuario_rol = flask_session.get('usuario_rol')
            if usuario_rol != RolEnum.ADMIN.value:
                return jsonify({"error": "No autorizado"}), 403
                
            data = request.json or {}
            valor = str(data.get('valor', '0.0'))
            try:
                val_float = float(valor)
                if val_float < 0:
                    raise ValueError()
            except ValueError:
                return jsonify({"error": "Precio mínimo no válido"}), 400
                
            config = session.query(Configuracion).filter_by(clave='precio_minimo_item').first()
            valor_previo = config.valor if config else '(no definido)'
            if not config:
                config = Configuracion(clave='precio_minimo_item', valor=valor)
                session.add(config)
            else:
                config.valor = valor
                
            log = LogAuditoria(
                usuario_id=flask_session.get('usuario_id'),
                accion="Configuración Modificada",
                detalles=f"Precio mínimo de item modificado: '${valor_previo}' -> '${valor}'"
            )
            session.add(log)
            session.commit()
            return jsonify({"mensaje": "Precio mínimo actualizado", "valor": valor}), 200
            
        else: # GET
            config = session.query(Configuracion).filter_by(clave='precio_minimo_item').first()
            valor = config.valor if config else '0.0'
            return jsonify({"valor": valor}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@precios_bp.route('/api/configuracion/<string:clave>', methods=['GET', 'POST'])
@login_required
def api_configuracion_generica(clave):
    """
    Endpoint genérico para obtener o guardar cualquier clave de configuración global.
    """
    session = Session()
    try:
        from flask import session as flask_session
        if request.method == 'POST':
            # Solo Administrador y Gerencia pueden guardar configuraciones
            usuario_rol = flask_session.get('usuario_rol')
            if usuario_rol not in [RolEnum.ADMIN.value, RolEnum.GERENCIA.value]:
                return jsonify({"error": "No autorizado"}), 403
                
            data = request.json or {}
            valor = str(data.get('valor', '')).strip()
            
            config = session.query(Configuracion).filter_by(clave=clave).first()
            valor_previo = config.valor if config else '(no definido)'
            if not config:
                config = Configuracion(clave=clave, valor=valor)
                session.add(config)
            else:
                config.valor = valor
                
            log = LogAuditoria(
                usuario_id=flask_session.get('usuario_id'),
                accion="Configuración Modificada",
                detalles=f"Configuración genérica '{clave}' modificada: '{valor_previo}' -> '{valor}'"
            )
            session.add(log)
            session.commit()
            return jsonify({"mensaje": f"Configuración {clave} actualizada", "valor": valor}), 200
            
        else: # GET
            config = session.query(Configuracion).filter_by(clave=clave).first()
            valor = config.valor if config else ''
            return jsonify({"valor": valor}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

# =================================================================
# API COTIZACIÓN EN VIVO (ACCESIBLE POR RECEPCIÓN/VENTAS/ADMIN)
# =================================================================
def calcular_precio_interno(session, data):
    """
    Calcula el costo estimado de una orden de trabajo basado en sus parámetros (versión interna).
    """
    tipo_trabajo = data.get('tipo_trabajo')
    material = data.get('material')
    cantidad = int(data.get('cantidad', 1))
    laminado = data.get('laminado', False)
    
    if material == 'Vinil Transparente':
        laminado = False
        
    # Manejar medidas de Sticker (ej. "3 Metros" o "1/2 Metro")
    medidas_texto = data.get('medidas', '')
    
    # Manejar dimensiones estándar
    ancho = data.get('medida_ancho')
    alto = data.get('medida_alto')
    unidad = data.get('medida_unidad', 'cm')
    
    if not tipo_trabajo or not material:
        return {"subtotal": 0.0, "area_m2": 0.0, "mensaje": "Seleccione tipo y material"}
        
    # 1. Obtener tarifa del material
    tarifa = session.query(PrecioMaterial).filter_by(tipo_trabajo=tipo_trabajo, material=material, es_adicional=False).first()
    if not tarifa:
        return {
            "subtotal": 0.0,
            "area_m2": 0.0,
            "mensaje": f"Precio no configurado para {tipo_trabajo} - {material}"
        }
        
    area_m2 = 0.0
    
    # 2. Calcular el área en metros cuadrados (m2)
    if tipo_trabajo == 'Sticker':
        metros = 1.0
        partes = medidas_texto.lower().split()
        if partes:
            try:
                # Si es un fraccionario ej: "1/2"
                if '/' in partes[0]:
                    num, den = partes[0].split('/')
                    metros = float(num) / float(den)
                else:
                    metros = float(partes[0])
            except ValueError:
                metros = 1.0
        area_m2 = metros
        cantidad = 1 # Para stickers la cantidad se ve reflejada en metros
    else:
        # Impresión, Impresión y Corte, Impresión UV, Banner, Corte Vinil, Corte Acrílico
        if ancho and alto:
            try:
                w = float(ancho)
                h = float(alto)
                # Convertir a metros
                if unidad == 'cm':
                    w /= 100.0
                    h /= 100.0
                elif unidad == 'mm':
                    w /= 1000.0
                    h /= 1000.0
                area_m2 = w * h
                if 0 < area_m2 < 0.05:
                    area_m2 = 0.05
            except ValueError:
                area_m2 = 1.0
        else:
            area_m2 = 1.0
                
    # 3. Calcular costo base y laminado
    costo_unitario_base = area_m2 * tarifa.precio_m2
    costo_unitario_laminado = 0.0
    precio_laminado_m2_val = 0.0
    
    if laminado and tipo_trabajo != 'Impresión UV' and material != 'Vinil Transparente':
        # Buscamos si hay un laminado configurado como acabado/adicional para este tipo de trabajo
        tarifa_laminado = session.query(PrecioMaterial).filter_by(
            tipo_trabajo=tipo_trabajo,
            material='Vinil Transparente',
            es_adicional=True
        ).first()
        if not tarifa_laminado:
            # Fallback general
            tarifa_laminado = session.query(PrecioMaterial).filter_by(
                material='Vinil Transparente',
                es_adicional=True
            ).first()
            
        if tarifa_laminado:
            precio_laminado_m2_val = tarifa_laminado.precio_m2
            costo_unitario_laminado = area_m2 * precio_laminado_m2_val
        
    # 4. Calcular acabados para Banner
    costo_unitario_acabado = 0.0
    if tipo_trabajo == 'Banner':
        acabado_banner = data.get('acabado_banner', '')
        material_bastidor = data.get('material_bastidor', '')
        
        if acabado_banner:
            nombre_acabado = acabado_banner
            if acabado_banner == 'Bastidor' and material_bastidor:
                nombre_acabado = f"Bastidor {material_bastidor}"
                
            tarifa_acabado = session.query(PrecioMaterial).filter_by(
                tipo_trabajo='Banner',
                material=nombre_acabado,
                es_adicional=True
            ).first()
            if tarifa_acabado:
                costo_unitario_acabado = area_m2 * tarifa_acabado.precio_m2
                
    # 4.5. Calcular costo de tablero PVC
    costo_unitario_pvc = 0.0
    instalacion_pvc = data.get('instalacion_pvc', False)
    grosor_pvc = data.get('grosor_pvc', '')
    tarifa_pvc = None
    
    if instalacion_pvc and grosor_pvc:
        grosor_limpio = str(grosor_pvc).strip()
        grosor_con_espacio = grosor_limpio
        if not ' ' in grosor_limpio and grosor_limpio.endswith('mm'):
            grosor_con_espacio = grosor_limpio.replace('mm', ' mm')
            
        tarifa_pvc = session.query(PrecioMaterial).filter(
            PrecioMaterial.tipo_trabajo == 'Tablero PVC',
            PrecioMaterial.material.in_([grosor_limpio, grosor_con_espacio]),
            PrecioMaterial.es_adicional == True
        ).first()
        if tarifa_pvc:
            costo_unitario_pvc = area_m2 * tarifa_pvc.precio_m2
                
    # Calcular costo unitario
    costo_unitario = costo_unitario_base + costo_unitario_laminado + costo_unitario_acabado + costo_unitario_pvc
    
    # Enforce minimum price per item
    config_minimo = session.query(Configuracion).filter_by(clave='precio_minimo_item').first()
    precio_minimo_item = float(config_minimo.valor) if config_minimo else 0.0
    
    if costo_unitario < precio_minimo_item:
        costo_unitario = precio_minimo_item
        
    subtotal = costo_unitario * cantidad
    
    # 5. Aplicar redondeo global configurado
    config_redondeo = session.query(Configuracion).filter_by(clave='tipo_redondeo').first()
    tipo_redondeo = config_redondeo.valor if config_redondeo else 'exacto'
    
    if tipo_redondeo == 'entero_superior':
        subtotal = float(math.ceil(subtotal))
    elif tipo_redondeo == 'decimal_cercano':
        subtotal = round(subtotal * 2.0) / 2.0
    else:
        subtotal = round(subtotal, 2)
        
    return {
        "subtotal": subtotal,
        "area_m2": round(area_m2, 3),
        "precio_m2": tarifa.precio_m2,
        "precio_laminado_m2": precio_laminado_m2_val,
        "precio_pvc_m2": tarifa_pvc.precio_m2 if tarifa_pvc else 0.0,
        "costo_base": round(costo_unitario_base * cantidad, 2),
        "costo_laminado": round(costo_unitario_laminado * cantidad, 2),
        "costo_pvc": round(costo_unitario_pvc * cantidad, 2),
        "costo_acabado": round(costo_unitario_acabado * cantidad, 2),
        "precio_minimo_aplicado": (costo_unitario == precio_minimo_item and precio_minimo_item > 0.0),
        "precio_minimo_valor": precio_minimo_item,
        "mensaje": "Cálculo exitoso"
    }

@precios_bp.route('/api/precios/calcular', methods=['POST'])
@login_required
def calcular_precio():
    """
    Calcula el costo estimado de una orden de trabajo basado en sus parámetros.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos"}), 400
        
    session = Session()
    try:
        res = calcular_precio_interno(session, data)
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
