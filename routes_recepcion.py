# ----------------------------------------------------------------------
# Copyright (c) 2026 Daniel Marin SysDev.
# Todos los derechos reservados.
# Este archivo es propiedad exclusiva de Daniel Marin.
# Queda prohibida su reproducción o distribución sin autorización.
# ----------------------------------------------------------------------
from flask import Blueprint, request, jsonify, render_template, session as flask_session
from database_models import engine, Cliente, OrdenTrabajo, EstadoOrdenEnum, LogAuditoria, Pedido, Usuario, RolEnum, Incidencia
from sqlalchemy.orm import sessionmaker
from file_manager import create_pedido_folders
from datetime import datetime
import utils_bcv
from routes_auth import login_required, role_required
import re

def extraer_monto_numerico(texto):
    if not texto:
        return 0.0
    match = re.search(r"[-+]?\d*\.?\d+", str(texto))
    if match:
        try:
            return float(match.group())
        except ValueError:
            return 0.0
    return 0.0

recepcion_bp = Blueprint('recepcion', __name__)
Session = sessionmaker(bind=engine)

@recepcion_bp.route('/api/ordenes', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def crear_orden_trabajo():
    """
    Endpoint para crear un Pedido Maestro y sus correspondientes Artículos (Órdenes).
    Espera JSON: { cliente_id, creador_id, referencia, articulos: [{nombre, specs}] }
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos"}), 400
        
    cliente_id = data.get('cliente_id')
    creador_id = data.get('creador_id')
    referencia = data.get('referencia', '')
    articulos = data.get('articulos', [])
    es_borrador = data.get('es_borrador', False)
    ocultar_precio_ventas = data.get('ocultar_precio_ventas', False)
    if flask_session.get('usuario_rol') not in [RolEnum.ADMIN.value, RolEnum.GERENCIA.value]:
        ocultar_precio_ventas = False
    
    if not cliente_id or not creador_id or not articulos:
        return jsonify({"error": "Faltan campos obligatorios o no hay artículos"}), 400
        
    session = Session()
    try:
        cliente = session.query(Cliente).filter_by(id=cliente_id).first()
        if not cliente:
            return jsonify({"error": "Cliente no existe"}), 404
            
        motivo_sin_costo = data.get('motivo_sin_costo', '').strip()
        monto_total = data.get('monto_total', None)
        
        # Validar que si no se cobra (monto_total es 0 o vacío), se especifique el porqué
        monto_total_val = 0.0
        if monto_total is not None:
            try:
                monto_total_val = float(monto_total)
            except (ValueError, TypeError):
                monto_total_val = 0.0
        
        if monto_total_val <= 0.0:
            if not motivo_sin_costo:
                return jsonify({"error": "Para pedidos sin costo, debe especificar el motivo (ej: Garantía, Cortesía, Muestra, etc.)"}), 400

        estado_pago = data.get('estado_pago', 'Por Cancelar')
        monto_abono = data.get('monto_abono', '')
        metodo_pago = data.get('metodo_pago', '')
        moneda = data.get('moneda', 'USD')
        tasa_bcv = data.get('tasa_bcv', None)

        # Calcular el valor numérico del abono ingresado manualmente
        abono_valor = 0.0
        if estado_pago == 'Abono' and monto_abono:
            abono_valor = extraer_monto_numerico(monto_abono)
        elif estado_pago == 'Cancelado':
            abono_valor = float(monto_total) if monto_total else 0.0

        # Aplicar saldo a favor si se solicita
        usar_saldo = data.get('usar_saldo_favor', False)
        saldo_aplicado = 0.0
        if usar_saldo and cliente.saldo_favor and cliente.saldo_favor > 0:
            saldo_aplicado = min(cliente.saldo_favor, float(monto_total) if monto_total else 0.0)
            cliente.saldo_favor -= saldo_aplicado
            abono_valor += saldo_aplicado
            
        # Determinar el estado final y el exceso
        if monto_total_val == 0.0:
            estado_pago = 'Cancelado'
            monto_abono = f"Sin Costo: {motivo_sin_costo}"
        elif monto_total is not None:
            abono_manual = extraer_monto_numerico(monto_abono)
            monto_restante = max(0.0, monto_total_val - abono_valor)
            
            # Construir desglose detallado para auditoría
            fuentes = []
            if abono_manual > 0:
                fuentes.append(f"${abono_manual:.2f} [{metodo_pago or 'No especificado'}]")
            if saldo_aplicado > 0:
                fuentes.append(f"${saldo_aplicado:.2f} [Saldo a favor]")
            desglose = " + ".join(fuentes) if fuentes else "Sin abonos previos"
            
            if abono_valor >= monto_total_val:
                estado_pago = 'Cancelado'
                exceso = abono_valor - monto_total_val
                if exceso > 0:
                    cliente.saldo_favor = (cliente.saldo_favor or 0.0) + exceso
                    monto_abono = f"Pagado con exceso. Abonó total: ${abono_valor:.2f} ({desglose}). Exceso de ${exceso:.2f} guardado a favor."
                else:
                    monto_abono = f"Pago completo. Abonó total: ${abono_valor:.2f} ({desglose})."
            elif abono_valor > 0:
                estado_pago = 'Abono'
                monto_abono = f"Abonado total: ${abono_valor:.2f} ({desglose}). Resta por pagar: ${monto_restante:.2f} USD."
            else:
                estado_pago = 'Por Cancelar'
                monto_abono = f"Pendiente de pago. Resta por pagar: ${monto_total_val:.2f} USD."

        # 1. Crear el Pedido Maestro
        nuevo_pedido = Pedido(
            cliente_id=cliente_id,
            referencia=referencia,
            estado_pago=estado_pago,
            monto_abono=monto_abono,
            metodo_pago=metodo_pago,
            monto_total=monto_total,
            moneda=moneda,
            tasa_bcv=tasa_bcv,
            ocultar_precio_ventas=ocultar_precio_ventas
        )
        session.add(nuevo_pedido)
        session.flush() # Para obtener nuevo_pedido.id
        
        # 2. Generar Carpetas del Pedido y Artículos
        rutas_articulos = []
        if es_borrador:
            nuevo_pedido.ruta_carpeta = None
            rutas_articulos = [None] * len(articulos)
        else:
            anio = datetime.utcnow().year
            mes = datetime.utcnow().month
            nombres_articulos = [a.get('tipo_trabajo', 'Articulo') for a in articulos]
            
            try:
                pedido_path, rutas_articulos = create_pedido_folders(
                    cliente_id=cliente.id,
                    pedido_id=nuevo_pedido.id,
                    articulos_nombres=nombres_articulos,
                    anio=anio,
                    mes=mes,
                    master_data_path=cliente.ruta_activos_permanentes
                )
                nuevo_pedido.ruta_carpeta = pedido_path
            except Exception as file_e:
                session.rollback()
                return jsonify({"error": "Error al crear las carpetas en el disco", "detalle": str(file_e)}), 500
            
        # 3. Crear cada Artículo (OrdenTrabajo)
        ordenes_creadas = []
        for idx, art_data in enumerate(articulos):
            tipo = art_data.get('tipo_trabajo', 'Artículo')
            material = art_data.get('material', '')
            
            # Lógica de medidas y cantidad
            if tipo == 'Sticker':
                medidas = art_data.get('medidas', '')
                cantidad = 1
            else:
                ancho = art_data.get('medida_ancho', '')
                alto = art_data.get('medida_alto', '')
                unidad = art_data.get('medida_unidad', 'cm')
                if ancho and alto:
                    medidas = f"{ancho}x{alto}{unidad}"
                else:
                    medidas = ''
                cantidad = int(art_data.get('cantidad', 1))
                
            specs_originales = art_data.get('specs', '')
            instalacion_pvc = art_data.get('instalacion_pvc', False)
            grosor_pvc = art_data.get('grosor_pvc', '')
            acabado_banner = art_data.get('acabado_banner', '')
            material_bastidor = art_data.get('material_bastidor', '')
            requiere_instalacion = art_data.get('requiere_instalacion', False)
            enlace_recursos = art_data.get('enlace_recursos', '')
            laminado = art_data.get('laminado', False)
            if tipo == 'Impresión UV':
                laminado = False
            
            # Formatear especificaciones con extras
            especificaciones_finales = specs_originales
            
            # Agregar enlace de recursos al final
            if enlace_recursos:
                nota_recursos = f"\n🔗 ENLACE A RECURSOS: {enlace_recursos}"
                especificaciones_finales = f"{especificaciones_finales}{nota_recursos}" if especificaciones_finales else f"🔗 ENLACE A RECURSOS: {enlace_recursos}"
            
            # Condicional Instalación General
            if requiere_instalacion:
                nota_inst = "[REQUIERE INSTALACIÓN EN SITIO]"
                especificaciones_finales = f"{nota_inst}\n{especificaciones_finales}" if especificaciones_finales else nota_inst
                
            # Condicional PVC
            if instalacion_pvc:
                nota_pvc = f"[REQUIERE INSTALACIÓN EN PVC - Grosor: {grosor_pvc}]"
                especificaciones_finales = f"{nota_pvc}\n{especificaciones_finales}" if especificaciones_finales else nota_pvc
                
            # Condicional Laminado
            if laminado:
                nota_lam = "[REQUIERE LAMINADO]"
                especificaciones_finales = f"{nota_lam}\n{especificaciones_finales}" if especificaciones_finales else nota_lam

            # Condicional Acabados Banner
            if acabado_banner:
                if acabado_banner == 'Bastidor':
                    nota_banner = f"[ACABADO BANNER: En Bastidor de {material_bastidor}]"
                elif acabado_banner == 'Ojetes':
                    nota_banner = "[ACABADO BANNER: Lleva Ojetes]"
                elif acabado_banner == 'Pendón Armado':
                    nota_banner = "[ACABADO BANNER: Pendón Armado]"
                else:
                    # Caso dinámico de la base de datos (ej: "Bastidor Madera", "Bastidor Metal")
                    nota_banner = f"[ACABADO BANNER: {acabado_banner}]"
                    
                if nota_banner:
                    especificaciones_finales = f"{nota_banner}\n{especificaciones_finales}" if especificaciones_finales else nota_banner
            
            # Construir nombre concatenado
            partes_nombre = []
            if cantidad > 1:
                partes_nombre.append(f"[{cantidad}x]")
            partes_nombre.append(tipo)
            if material:
                partes_nombre.append(f"- {material}")
            if laminado:
                partes_nombre.append("+ Laminado")
            if medidas:
                partes_nombre.append(f"({medidas})")
                
            # Si se solicita duplicar un artículo histórico
            duplicar_de_id = art_data.get('duplicar_de_articulo_id')
            nombre_manual = art_data.get('nombre_proyecto_manual')
            
            if duplicar_de_id and nombre_manual:
                nombre_final = nombre_manual
            else:
                nombre_final = " ".join(partes_nombre)
            
            # Asignar diseñador si fue seleccionado
            disenador_id = art_data.get('disenador_id')
            if disenador_id == "":
                disenador_id = None
            
            requiere_cotiz = art_data.get('requiere_cotizacion_especial', False)
            nueva_orden = OrdenTrabajo(
                pedido_id=nuevo_pedido.id,
                cliente_id=cliente_id,
                nombre_proyecto=nombre_final,
                especificaciones=especificaciones_finales,
                estado=EstadoOrdenEnum.BORRADOR if es_borrador else EstadoOrdenEnum.PENDIENTE,
                ruta_archivos_transaccionales=rutas_articulos[idx],
                disenador_id=disenador_id,
                requiere_cotizacion=requiere_cotiz
            )
            session.add(nueva_orden)
            
            # Si tiene duplicar_de_id, copiar archivos físicos
            if duplicar_de_id:
                try:
                    import shutil
                    orden_orig = session.query(OrdenTrabajo).filter_by(id=int(duplicar_de_id)).first()
                    if orden_orig and orden_orig.ruta_archivos_transaccionales and os.path.exists(orden_orig.ruta_archivos_transaccionales):
                        orig_dir = orden_orig.ruta_archivos_transaccionales
                        dest_dir = rutas_articulos[idx]
                        
                        # Copiar subcarpetas
                        for sub in ['Editable', 'Salida_Impresion', 'Muestras']:
                            sub_orig = os.path.join(orig_dir, sub)
                            sub_dest = os.path.join(dest_dir, sub)
                            if os.path.exists(sub_orig):
                                for item in os.listdir(sub_orig):
                                    s = os.path.join(sub_orig, item)
                                    d = os.path.join(sub_dest, item)
                                    if os.path.isfile(s):
                                        try:
                                            shutil.copy2(s, d)
                                        except Exception:
                                            pass
                        # Copiar perfil_impresion.txt si existe
                        for item in os.listdir(orig_dir):
                            s = os.path.join(orig_dir, item)
                            d = os.path.join(dest_dir, item)
                            if os.path.isfile(s) and (item.endswith('.txt') or item.endswith('.pdf')):
                                try:
                                    shutil.copy2(s, d)
                                except Exception:
                                    pass
                except Exception as copy_err:
                    import logging
                    logging.warning(f"No se pudieron copiar los archivos del histórico: {copy_err}")
            
            # Si requiere cotización especial y NO es borrador (flujo activo), crear alerta de incidencia
            if requiere_cotiz and not es_borrador:
                incidencia = Incidencia(
                    reportado_por_id=creador_id,
                    orden=nueva_orden,
                    tipo_problema="Cotización Especial",
                    detalles="Esta orden requiere un presupuesto manual asignado por Gerencia.",
                    estado="Pendiente"
                )
                session.add(incidencia)
                
            ordenes_creadas.append(nueva_orden)
            
        # Registrar auditoría
        log = LogAuditoria(
            usuario_id=creador_id,
            accion="Pedido Creado",
            detalles=f"Pedido #{nuevo_pedido.id} creado con {len(articulos)} artículos para {cliente.nombre_empresa}"
        )
        session.add(log)
        
        session.commit()
        
        return jsonify({
            "mensaje": "Pedido generado exitosamente",
            "pedido_id": nuevo_pedido.id,
            "articulos_creados": len(articulos),
            "ruta_archivos": nuevo_pedido.ruta_carpeta
        }), 201
        
    except Exception as e:
        session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Ocurrió un error en el servidor", "detalle": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/clientes', methods=['GET'])
def obtener_clientes():
    """
    Endpoint auxiliar para que Recepción pueda obtener la lista de clientes
    y mostrarlos en un menú desplegable al crear la orden.
    """
    session = Session()
    try:
        clientes = session.query(Cliente).all()
        resultado = []
        for c in clientes:
            # Buscar si el cliente tiene pedidos pendientes de pago
            pedidos_pendientes = session.query(Pedido).filter(
                Pedido.cliente_id == c.id,
                Pedido.estado_pago.in_(["Por Cancelar", "Abono"])
            ).count()
            
            resultado.append({
                "id": c.id,
                "nombre_empresa": c.nombre_empresa,
                "contacto_nombre": c.contacto_nombre,
                "deuda_pendiente": pedidos_pendientes > 0,
                "cantidad_pedidos_pendientes": pedidos_pendientes,
                "saldo_favor": c.saldo_favor or 0.0
            })
            
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/disenadores', methods=['GET'])
def obtener_disenadores():
    session = Session()
    try:
        # Solo usuarios con rol DISENADOR
        disenadores = session.query(Usuario).filter_by(rol=RolEnum.DISENADOR).all()
        resultado = []
        for d in disenadores:
            # Contar tareas activas (que no estén completadas o listas para entregar)
            tareas_activas = session.query(OrdenTrabajo).filter(
                OrdenTrabajo.disenador_id == d.id,
                OrdenTrabajo.estado.in_([EstadoOrdenEnum.EN_DISENO, EstadoOrdenEnum.EN_REVISION])
            ).count()
            
            resultado.append({
                "id": d.id,
                "nombre": d.nombre,
                "carga_trabajo": tareas_activas
            })
            
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/ordenes/<int:orden_id>/estado', methods=['PUT'])
def actualizar_estado_orden(orden_id):
    """
    Endpoint para que Diseñadores o Producción cambien el estado de un trabajo.
    Espera un JSON con:
    - nuevo_estado (str)
    - usuario_id (int) -> El ID del usuario que hace el cambio
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos"}), 400
        
    nuevo_estado_str = data.get('nuevo_estado')
    usuario_id = data.get('usuario_id')
    
    if not nuevo_estado_str or not usuario_id:
        return jsonify({"error": "Faltan campos: nuevo_estado, usuario_id"}), 400
        
    # Validar que el estado enviado sea válido en el Enum
    try:
        nuevo_estado = EstadoOrdenEnum(nuevo_estado_str)
    except ValueError:
        return jsonify({"error": f"Estado inválido. Opciones válidas: {[e.value for e in EstadoOrdenEnum]}"}), 400
        
    session = Session()
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden:
            return jsonify({"error": f"Orden con ID {orden_id} no encontrada"}), 404
            
        estado_anterior = orden.estado.value
        orden.estado = nuevo_estado
        
        # Registrar en logs de auditoría el cambio
        log = LogAuditoria(
            usuario_id=usuario_id,
            orden_id=orden.id,
            accion="Cambio de Estado",
            detalles=f"Orden #{orden_id} pasó de '{estado_anterior}' a '{nuevo_estado.value}'"
        )
        session.add(log)
        
        # --- LÓGICA DE HOT FOLDERS ---
        if nuevo_estado == EstadoOrdenEnum.APROBADO_IMPRIMIR and orden.ruta_archivos_transaccionales:
            from file_manager import vincular_archivos_a_hot_folder
            from datetime import datetime
            
            # Inferir máquina
            nombre_lower = orden.nombre_proyecto.lower()
            if "corte vinil" in nombre_lower:
                maquina = "PLOTTER_CORTE"
            elif "laser" in nombre_lower:
                maquina = "LASER"
            elif "cnc" in nombre_lower or "corpórea" in nombre_lower:
                maquina = "CNC"
            elif "uv" in nombre_lower:
                maquina = "IMPRESORA_UV"
            else:
                maquina = "PLOTTER"
                
            hoy = datetime.now()
            meses = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
            mes_formato = f"{hoy.month:02d}{meses[hoy.month - 1]}"
            
            cliente_nombre = orden.cliente.nombre_empresa if orden.cliente else "CLIENTE_DESCONOCIDO"
            # El nombre_proyecto ya trae cantidad, material y medidas (ej: "[2x] Impresión - Vinil (10x10cm)")
            prefijo = f"{cliente_nombre} - {orden.nombre_proyecto} [P{orden.pedido_id}_A{orden.id}]"
            
            vincular_archivos_a_hot_folder(
                articulo_path=orden.ruta_archivos_transaccionales,
                maquina=maquina,
                anio=hoy.year,
                mes_nombre=mes_formato,
                dia=hoy.day,
                prefijo_nombre=prefijo
            )
            
            # Vincular archivos editables al repositorio permanente del cliente
            from file_manager import vincular_editable_a_cliente
            if orden.cliente and orden.cliente.ruta_activos_permanentes:
                vincular_editable_a_cliente(
                    articulo_path=orden.ruta_archivos_transaccionales,
                    cliente_activos_path=orden.cliente.ruta_activos_permanentes,
                    prefijo_nombre=prefijo
                )
        # ------------------------------
        
        # ---------------------------------
        
        session.commit()
        
        return jsonify({
            "mensaje": "Estado actualizado exitosamente",
            "orden_id": orden.id,
            "nuevo_estado": orden.estado.value
        }), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": "Ocurrió un error en el servidor", "detalle": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/siguiente-referencia', methods=['GET'])
def siguiente_referencia():
    """Genera una referencia secuencial diaria (ej: REF-260518-001)"""
    session = Session()
    try:
        hoy = datetime.utcnow()
        prefijo = f"REF-{hoy.strftime('%y%m%d')}-"
        
        # Buscar el último pedido con este prefijo
        ultimo_pedido = session.query(Pedido).filter(
            Pedido.referencia.like(f"{prefijo}%")
        ).order_by(Pedido.id.desc()).first()
        
        if ultimo_pedido and ultimo_pedido.referencia.startswith(prefijo):
            try:
                # Extraer la parte final y sumar 1
                ultimo_num = int(ultimo_pedido.referencia.split('-')[-1])
                siguiente = ultimo_num + 1
            except ValueError:
                siguiente = 1
        else:
            siguiente = 1
            
        return jsonify({"referencia": f"{prefijo}{siguiente:03d}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/bcv', methods=['GET'])
def get_bcv_rate():
    """Retorna la tasa del BCV actual (en caché por 12 horas) redondeda a 2 decimales"""
    tasa = utils_bcv.get_tasa_bcv()
    if tasa:
        return jsonify({"tasa": round(tasa, 2)}), 200
    else:
        return jsonify({"error": "No se pudo obtener la tasa del BCV"}), 500

# -------------------------------------------------------------------
# Endpoints de Incidencias en Planta
# -------------------------------------------------------------------

@recepcion_bp.route('/api/ordenes/<int:orden_id>/incidencias', methods=['POST'])
@login_required
def reportar_incidencia(orden_id):
    """
    Registra una incidencia sobre una orden de trabajo y alerta por WhatsApp al Admin.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos"}), 400
        
    usuario_id = data.get('usuario_id')
    tipo_problema = data.get('tipo_problema')
    detalles = data.get('detalles')
    
    if not usuario_id or not tipo_problema or not detalles:
        return jsonify({"error": "Faltan campos obligatorios: usuario_id, tipo_problema, detalles"}), 400
        
    session = Session()
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden:
            return jsonify({"error": "Orden no encontrada"}), 404
            
        usuario = session.query(Usuario).filter_by(id=usuario_id).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
        # Crear Incidencia
        incidencia = Incidencia(
            reportado_por_id=usuario_id,
            orden_id=orden_id,
            tipo_problema=tipo_problema,
            detalles=detalles,
            estado="Pendiente"
        )
        session.add(incidencia)
        
        # Auditoría
        log = LogAuditoria(
            usuario_id=usuario_id,
            orden_id=orden_id,
            accion="Reporte Incidencia",
            detalles=f"Incidencia de tipo '{tipo_problema}' reportada. Detalles: {detalles}"
        )
        session.add(log)
        session.commit()
        
        return jsonify({"mensaje": "Incidencia reportada con éxito", "incidencia_id": incidencia.id}), 201
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/incidencias/<int:incidencia_id>/resolver', methods=['PUT'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def resolver_incidencia(incidencia_id):
    """
    Marca una incidencia reportada como resuelta.
    """
    data = request.json or {}
    usuario_id = flask_session.get('usuario_id') or data.get('usuario_id', 1)
    
    session = Session()
    try:
        incidencia = session.query(Incidencia).filter_by(id=incidencia_id).first()
        if not incidencia:
            return jsonify({"error": "Incidencia no encontrada"}), 404
            
        incidencia.estado = "Resuelto"
        
        # Lógica especial para Cotización Especial
        monto_detalles = ""
        if incidencia.tipo_problema == "Cotización Especial":
            monto_aprobado = data.get('monto_aprobado')
            if monto_aprobado is not None:
                try:
                    monto_float = float(monto_aprobado)
                    orden = incidencia.orden
                    if orden and orden.pedido:
                        pedido = orden.pedido
                        pedido.monto_total = monto_float
                        
                        # Actualizar si se oculta o no a ventas
                        ocultar_precio = data.get('ocultar_precio_ventas', False)
                        pedido.ocultar_precio_ventas = ocultar_precio
                        
                        # Recalcular estados de pago
                        abono_valor = extraer_monto_numerico(pedido.monto_abono)
                        monto_restante = max(0.0, monto_float - abono_valor)
                        
                        if abono_valor >= monto_float:
                            pedido.estado_pago = 'Cancelado'
                            pedido.monto_abono = f"Pago completo. Abonó total: ${abono_valor:.2f}."
                        elif abono_valor > 0:
                            pedido.estado_pago = 'Abono'
                            pedido.monto_abono = f"Abonado total: ${abono_valor:.2f}. Resta por pagar: ${monto_restante:.2f} USD."
                        else:
                            pedido.estado_pago = 'Por Cancelar'
                            pedido.monto_abono = f"Pendiente de pago. Resta por pagar: ${monto_float:.2f} USD."
                        
                        orden.requiere_cotizacion = False
                        monto_detalles = f" Monto asignado: ${monto_float:.2f} USD (Ocultar a ventas: {ocultar_precio})."
                except ValueError:
                    return jsonify({"error": "Monto aprobado inválido"}), 400
        
        # Auditoría
        log = LogAuditoria(
            usuario_id=usuario_id,
            orden_id=incidencia.orden_id,
            accion="Resolución Incidencia",
            detalles=f"Incidencia #{incidencia_id} ({incidencia.tipo_problema}) resuelta.{monto_detalles}"
        )
        session.add(log)
        session.commit()
        
        return jsonify({"mensaje": "Incidencia marcada como resuelta"}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/ordenes/<int:orden_id>/incidencias', methods=['GET'])
@login_required
def obtener_incidencias_orden(orden_id):
    """
    Retorna la lista de incidencias reportadas para una orden de trabajo.
    """
    session = Session()
    try:
        incidencias = session.query(Incidencia).filter_by(orden_id=orden_id).order_by(Incidencia.fecha_creacion.desc()).all()
        resultado = []
        for inc in incidencias:
            resultado.append({
                "id": inc.id,
                "reportado_por": inc.reportado_por.nombre if inc.reportado_por else "Desconocido",
                "tipo_problema": inc.tipo_problema,
                "detalles": inc.detalles,
                "fecha": inc.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                "estado": inc.estado
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/recepcion/nueva-orden', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def vista_nueva_orden():
    """
    Vista de nueva orden / recepción de pedidos.
    """
    return render_template('recepcion.html')

# =================================================================
# MODULO DE BORRADORES GENERADOS POR EL BOT
# =================================================================
@recepcion_bp.route('/recepcion/borradores', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def vista_borradores():
    """
    Renderiza la vista de administración de borradores generados por el Bot.
    """
    return render_template('borradores.html')

@recepcion_bp.route('/api/borradores', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def listar_borradores():
    """
    Retorna la lista de órdenes en estado BORRADOR.
    """
    session = Session()
    try:
        borradores = session.query(OrdenTrabajo).filter_by(estado=EstadoOrdenEnum.BORRADOR).all()
        res = []
        for b in borradores:
            es_bot = (b.pedido.referencia == "Borrador Bot") if b.pedido else False
            res.append({
                "id": b.id,
                "pedido_id": b.pedido_id,
                "cliente_id": b.cliente_id,
                "cliente_nombre": b.cliente.nombre_empresa if b.cliente else "Desconocido",
                "cliente_telefono": b.cliente.telefono if b.cliente else "",
                "nombre_proyecto": b.nombre_proyecto,
                "especificaciones": b.especificaciones,
                "fecha_creacion": b.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                "monto_total": b.pedido.monto_total if b.pedido else 0.0,
                "cliente_saldo_favor": b.cliente.saldo_favor or 0.0 if b.cliente else 0.0,
                "es_bot": es_bot
            })
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/borradores/<int:orden_id>/confirmar', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def confirmar_borrador(orden_id):
    """
    Confirma un borrador, crea su estructura de carpetas físicas en el servidor,
    asigna un diseñador si se especifica, y cambia su estado a PENDIENTE (flujo activo).
    """
    session = Session()
    data = request.json or {}
    usuario_id = flask_session.get('usuario_id') or 1  # Creador / Confirmador
    
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden:
            return jsonify({"error": "Borrador no encontrado"}), 404
            
        pedido = orden.pedido
        if not pedido:
            return jsonify({"error": "Pedido asociado no encontrado"}), 404
            
        # Actualizar los datos del pedido con el formulario de confirmación
        referencia = data.get('referencia', f"PED-{pedido.id}")
        estado_pago = data.get('estado_pago', 'Por Cancelar')
        monto_abono = str(data.get('monto_abono', '0'))
        metodo_pago = data.get('metodo_pago', '')
        monto_total = float(data.get('monto_total', pedido.monto_total))
        moneda = data.get('moneda', 'USD')
        tasa_bcv = float(data.get('tasa_bcv', 0.0))
        disenador_id = data.get('disenador_id')
        
        # Validar motivo sin costo si total es 0
        motivo_sin_costo = data.get('motivo_sin_costo', '').strip()
        if monto_total <= 0.0:
            if not motivo_sin_costo:
                motivo_sin_costo = data.get('notas_pago', '').strip()
            if not motivo_sin_costo:
                return jsonify({"error": "Para pedidos sin costo, debe especificar el motivo (ej: Garantía, Cortesía, Muestra, etc.)"}), 400

        # Obtener el cliente
        cliente = pedido.cliente

        # Calcular el valor numérico del abono ingresado manualmente
        abono_valor = 0.0
        if estado_pago == 'Abono' and monto_abono:
            abono_valor = extraer_monto_numerico(monto_abono)
        elif estado_pago == 'Cancelado':
            abono_valor = float(monto_total)
            
        # Aplicar saldo a favor si se solicita
        usar_saldo = data.get('usar_saldo_favor', False)
        saldo_aplicado = 0.0
        if usar_saldo and cliente and cliente.saldo_favor and cliente.saldo_favor > 0:
            saldo_aplicado = min(cliente.saldo_favor, float(monto_total))
            cliente.saldo_favor -= saldo_aplicado
            abono_valor += saldo_aplicado

        # Determinar el estado final y el exceso
        if monto_total == 0.0:
            estado_pago = 'Cancelado'
            monto_abono = f"Sin Costo: {motivo_sin_costo}"
        else:
            abono_manual = extraer_monto_numerico(monto_abono)
            monto_restante = max(0.0, monto_total - abono_valor)
            
            # Construir desglose detallado para auditoría
            fuentes = []
            if abono_manual > 0:
                fuentes.append(f"${abono_manual:.2f} [{metodo_pago or 'No especificado'}]")
            if saldo_aplicado > 0:
                fuentes.append(f"${saldo_aplicado:.2f} [Saldo a favor]")
            desglose = " + ".join(fuentes) if fuentes else "Sin abonos previos"
            
            if abono_valor >= monto_total:
                estado_pago = 'Cancelado'
                exceso = abono_valor - monto_total
                if exceso > 0 and cliente:
                    cliente.saldo_favor = (cliente.saldo_favor or 0.0) + exceso
                    monto_abono = f"Pagado con exceso. Abonó total: ${abono_valor:.2f} ({desglose}). Exceso de ${exceso:.2f} guardado a favor."
                else:
                    monto_abono = f"Pago completo. Abonó total: ${abono_valor:.2f} ({desglose})."
            elif abono_valor > 0:
                estado_pago = 'Abono'
                monto_abono = f"Abonado total: ${abono_valor:.2f} ({desglose}). Resta por pagar: ${monto_restante:.2f} USD."
            else:
                estado_pago = 'Por Cancelar'
                monto_abono = f"Pendiente de pago. Resta por pagar: ${monto_total:.2f} USD."
        
        pedido.referencia = referencia
        pedido.estado_pago = estado_pago
        pedido.monto_abono = monto_abono
        pedido.metodo_pago = metodo_pago
        pedido.monto_total = monto_total
        pedido.moneda = moneda
        pedido.tasa_bcv = tasa_bcv
        ocultar_precio_val = data.get('ocultar_precio_ventas', False)
        if flask_session.get('usuario_rol') not in [RolEnum.ADMIN.value, RolEnum.GERENCIA.value]:
            ocultar_precio_val = False
        pedido.ocultar_precio_ventas = ocultar_precio_val
        
        if disenador_id:
            orden.disenador_id = int(disenador_id)
            
        # Generar las carpetas del pedido
        from file_manager import create_pedido_folders
        from datetime import datetime
        
        anio = datetime.utcnow().year
        mes = datetime.utcnow().month
        
        cliente = orden.cliente
        pedido_path, rutas_articulos = create_pedido_folders(
            cliente_id=cliente.id,
            pedido_id=pedido.id,
            articulos_nombres=[orden.nombre_proyecto],
            anio=anio,
            mes=mes,
            master_data_path=cliente.ruta_activos_permanentes
        )
        
        pedido.ruta_carpeta = pedido_path
        orden.ruta_archivos_transaccionales = rutas_articulos[0]
        orden.estado = EstadoOrdenEnum.PENDIENTE # Cambiar de BORRADOR a PENDIENTE
        
        # Si requiere cotización especial, generar alerta de incidencia
        if orden.requiere_cotizacion:
            # Verificar si ya existe una incidencia de cotización pendiente
            existe = session.query(Incidencia).filter_by(orden_id=orden.id, tipo_problema="Cotización Especial", estado="Pendiente").first()
            if not existe:
                incidencia = Incidencia(
                    reportado_por_id=usuario_id,
                    orden_id=orden.id,
                    tipo_problema="Cotización Especial",
                    detalles="Esta orden requiere un presupuesto manual asignado por Gerencia.",
                    estado="Pendiente"
                )
                session.add(incidencia)
        
        # Registrar Auditoría
        log = LogAuditoria(
            usuario_id=usuario_id,
            orden_id=orden.id,
            accion="Confirmación Borrador",
            detalles=f"Borrador de orden #{orden.id} confirmado y activado en producción."
        )
        session.add(log)
        session.commit()
        
        return jsonify({"mensaje": "Borrador confirmado exitosamente", "orden_id": orden.id}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/borradores/<int:orden_id>/editar', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def editar_borrador(orden_id):
    """
    Edita los detalles de un borrador de orden antes de ser confirmado.
    """
    session = Session()
    data = request.json or {}
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden:
            return jsonify({"error": "Borrador no encontrado"}), 404
            
        nombre_proyecto = data.get('nombre_proyecto')
        especificaciones = data.get('especificaciones')
        monto_total = data.get('monto_total')
        
        if nombre_proyecto:
            orden.nombre_proyecto = nombre_proyecto
        if especificaciones:
            orden.especificaciones = especificaciones
        if monto_total is not None and orden.pedido:
            orden.pedido.monto_total = float(monto_total)
            
        session.commit()
        return jsonify({"mensaje": "Borrador actualizado exitosamente"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/borradores/<int:orden_id>', methods=['DELETE'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.VENTAS)
def eliminar_borrador(orden_id):
    """
    Elimina un borrador del sistema (rechazo).
    """
    session = Session()
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden:
            return jsonify({"error": "Borrador no encontrado"}), 404
            
        # Eliminar el pedido y el artículo
        pedido = orden.pedido
        if pedido:
            session.delete(pedido)
        session.delete(orden)
        session.commit()
        return jsonify({"mensaje": "Borrador eliminado exitosamente"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/ordenes/articulo/<int:articulo_id>/repetir', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.VENTAS)
def repetir_articulo_orden(articulo_id):
    """
    Duplica un artículo existente (OrdenTrabajo) en un nuevo Pedido.
    Espera JSON: { creador_id: int, requiere_modificacion: bool }
    """
    import os
    import shutil
    
    data = request.json or {}
    creador_id = data.get('creador_id')
    requiere_modificacion = data.get('requiere_modificacion', False)
    
    if not creador_id:
        return jsonify({"error": "Falta el ID del creador"}), 400
        
    session = Session()
    try:
        orden_original = session.query(OrdenTrabajo).filter_by(id=articulo_id).first()
        if not orden_original:
            return jsonify({"error": "Artículo no encontrado"}), 404
            
        cliente = orden_original.cliente
        if not cliente:
            return jsonify({"error": "Cliente asociado no existe"}), 404
            
        pedido_original = orden_original.pedido
        
        # 1. Crear el nuevo Pedido Maestro con datos copiados
        referencia_original = pedido_original.referencia if pedido_original else ""
        nuevo_pedido = Pedido(
            cliente_id=cliente.id,
            referencia=f"Reimpresión de {referencia_original or f'Orden #{articulo_id}'}".strip(),
            estado_pago="Por Cancelar",
            monto_abono="Pendiente por cobro de duplicado",
            metodo_pago=pedido_original.metodo_pago if pedido_original else "",
            monto_total=pedido_original.monto_total if pedido_original else 0.0,
            moneda=pedido_original.moneda if pedido_original else "USD",
            tasa_bcv=pedido_original.tasa_bcv if pedido_original else None,
            ocultar_precio_ventas=pedido_original.ocultar_precio_ventas if pedido_original else False
        )
        session.add(nuevo_pedido)
        session.flush() # Obtener nuevo_pedido.id
        
        # 2. Generar carpetas físicas para la nueva orden
        anio = datetime.utcnow().year
        mes = datetime.utcnow().month
        
        try:
            pedido_path, rutas_articulos = create_pedido_folders(
                cliente_id=cliente.id,
                pedido_id=nuevo_pedido.id,
                articulos_nombres=[orden_original.nombre_proyecto],
                anio=anio,
                mes=mes,
                master_data_path=cliente.ruta_activos_permanentes
            )
            nuevo_pedido.ruta_carpeta = pedido_path
            nueva_ruta_articulo = rutas_articulos[0]
        except Exception as file_e:
            session.rollback()
            return jsonify({"error": "Error al crear las carpetas físicas para el duplicado", "detalle": str(file_e)}), 500
            
        # 3. Copiar archivos desde el artículo original si existen
        if orden_original.ruta_archivos_transaccionales and os.path.exists(orden_original.ruta_archivos_transaccionales):
            orig_dir = orden_original.ruta_archivos_transaccionales
            dest_dir = nueva_ruta_articulo
            
            # Copiar archivos de 'Editable', 'Salida_Impresion', 'Muestras'
            subcarpetas = ['Editable', 'Salida_Impresion', 'Muestras']
            for sub in subcarpetas:
                sub_orig = os.path.join(orig_dir, sub)
                sub_dest = os.path.join(dest_dir, sub)
                if os.path.exists(sub_orig):
                    for item in os.listdir(sub_orig):
                        s = os.path.join(sub_orig, item)
                        d = os.path.join(sub_dest, item)
                        if os.path.isfile(s):
                            try:
                                shutil.copy2(s, d)
                            except Exception as copy_err:
                                logger.warning(f"No se pudo copiar archivo {s} a {d}: {copy_err}")
                                
            # Copiar perfil_impresion.txt o notas adicionales en la raíz si existen
            for item in os.listdir(orig_dir):
                s = os.path.join(orig_dir, item)
                d = os.path.join(dest_dir, item)
                if os.path.isfile(s) and (item.endswith('.txt') or item.endswith('.pdf')):
                    try:
                        shutil.copy2(s, d)
                    except Exception:
                        pass
                        
        # 4. Crear el nuevo Artículo (OrdenTrabajo)
        estado_final = EstadoOrdenEnum.APROBADO_IMPRIMIR if not requiere_modificacion else EstadoOrdenEnum.EN_DISENO
        
        nueva_orden = OrdenTrabajo(
            pedido_id=nuevo_pedido.id,
            cliente_id=cliente.id,
            nombre_proyecto=orden_original.nombre_proyecto,
            estado=estado_final,
            especificaciones=f"[DUPLICADO DE ARTÍCULO #{articulo_id}]\n{orden_original.especificaciones or ''}".strip(),
            ruta_archivos_transaccionales=nueva_ruta_articulo,
            disenador_id=orden_original.disenador_id
        )
        session.add(nueva_orden)
        session.flush()
        
        # 5. Si es aprobado para imprimir (sin modificación), vincular inmediatamente a Hot Folders
        if estado_final == EstadoOrdenEnum.APROBADO_IMPRIMIR:
            from file_manager import vincular_archivos_a_hot_folder, vincular_editable_a_cliente
            
            # Inferir máquina
            nombre_lower = nueva_orden.nombre_proyecto.lower()
            if "corte vinil" in nombre_lower:
                maquina = "PLOTTER_CORTE"
            elif "laser" in nombre_lower:
                maquina = "LASER"
            elif "cnc" in nombre_lower or "corpórea" in nombre_lower:
                maquina = "CNC"
            elif "uv" in nombre_lower:
                maquina = "IMPRESORA_UV"
            else:
                maquina = "PLOTTER"
                
            hoy = datetime.now()
            meses = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
            mes_formato = f"{hoy.month:02d}{meses[hoy.month - 1]}"
            
            cliente_nombre = cliente.nombre_empresa if cliente.nombre_empresa else "CLIENTE_DESCONOCIDO"
            prefijo = f"{cliente_nombre} - {nueva_orden.nombre_proyecto} [P{nueva_orden.pedido_id}_A{nueva_orden.id}]"
            
            vincular_archivos_a_hot_folder(
                articulo_path=nueva_ruta_articulo,
                maquina=maquina,
                anio=hoy.year,
                mes_nombre=mes_formato,
                dia=hoy.day,
                prefijo_nombre=prefijo
            )
            
            if cliente.ruta_activos_permanentes:
                vincular_editable_a_cliente(
                    articulo_path=nueva_ruta_articulo,
                    cliente_activos_path=cliente.ruta_activos_permanentes,
                    prefijo_nombre=prefijo
                )
                
        # Registrar auditoría
        log = LogAuditoria(
            usuario_id=creador_id,
            orden_id=nueva_orden.id,
            action=None, # Evitar conflictos, usar 'accion'
            accion="Duplicado Orden",
            detalles=f"Artículo #{articulo_id} duplicado como nueva Orden #{nueva_orden.id} (Requiere Modificación: {requiere_modificacion})"
        )
        session.add(log)
        session.commit()
        
        return jsonify({
            "mensaje": "Artículo duplicado exitosamente",
            "pedido_id": nuevo_pedido.id,
            "orden_id": nueva_orden.id,
            "estado": estado_final.value
        }), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/clientes/<int:cliente_id>/historico-articulos', methods=['GET'])
@login_required
def obtener_historico_articulos_cliente(cliente_id):
    """
    Retorna la lista de artículos previos (OrdenTrabajo) de un cliente específico,
    para que puedan ser repetidos desde la pantalla de creación de órdenes.
    """
    session = Session()
    try:
        ordenes = session.query(OrdenTrabajo).filter(
            OrdenTrabajo.cliente_id == cliente_id
        ).order_by(OrdenTrabajo.fecha_creacion.desc()).all()
        
        resultado = []
        vistos = set()
        for o in ordenes:
            if o.nombre_proyecto not in vistos:
                vistos.add(o.nombre_proyecto)
                resultado.append({
                    "id": o.id,
                    "nombre_proyecto": o.nombre_proyecto,
                    "especificaciones": o.especificaciones or "",
                    "disenador_id": o.disenador_id,
                    "fecha": o.fecha_creacion.strftime("%Y-%m-%d")
                })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@recepcion_bp.route('/api/ordenes/<int:orden_id>/cancelar', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS)
def cancelar_orden(orden_id):
    """
    Cancela una orden de trabajo (artículo).
    Si ya pagó o abonó, se puede retornar parte o el total del dinero como Saldo a Favor del cliente.
    Si estaba en cola de producción (Hot Folder), se rompen los enlaces.
    """
    data = request.json or {}
    motivo = data.get('motivo', 'Cancelado por solicitud del cliente')
    
    # Obtener el ID del usuario directamente de la sesión
    from flask import session as flask_session
    usuario_id = flask_session.get('usuario_id', 1)
    
    try:
        saldo_a_devolver = float(data.get('saldo_a_devolver', 0.0))
    except (TypeError, ValueError):
        saldo_a_devolver = 0.0
        
    session = Session()
    try:
        orden = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not orden:
            return jsonify({"error": "Orden no encontrada"}), 404
            
        cliente = orden.cliente
        if not cliente:
            return jsonify({"error": "Cliente no encontrado"}), 404
            
        if orden.estado == EstadoOrdenEnum.CANCELADO:
            return jsonify({"mensaje": "La orden ya se encuentra cancelada."}), 200
            
        estado_anterior = orden.estado.value
        orden.estado = EstadoOrdenEnum.CANCELADO
        
        # Devolver el saldo a favor si se solicita
        if saldo_a_devolver > 0:
            cliente.saldo_favor = (cliente.saldo_favor or 0.0) + saldo_a_devolver
            detalles_saldo = f" Se acreditaron ${saldo_a_devolver:.2f} USD como saldo a favor del cliente."
        else:
            detalles_saldo = ""
            
        # Eliminar archivos de la cola de producción (Hot Folder) si estaban enlazados
        import os
        from file_manager import BASE_DIR
        cola_dir = os.path.join(BASE_DIR, "Cola_Produccion")
        maquinas = ['PLOTTER', 'PLOTTER_CORTE', 'IMPRESORA_UV', 'LASER', 'CNC']
        patron = f"[P{orden.pedido_id}_A{orden.id}]"
        
        archivos_eliminados = []
        if os.path.exists(cola_dir):
            for m in maquinas:
                for sub in ['', 'Procesando']:
                    dir_ruta = os.path.join(cola_dir, m, sub)
                    if os.path.exists(dir_ruta):
                        for f in os.listdir(dir_ruta):
                            if patron in f:
                                path_f = os.path.join(dir_ruta, f)
                                if os.path.isfile(path_f):
                                    try:
                                        os.remove(path_f)
                                        archivos_eliminados.append(f)
                                    except Exception as err:
                                        import logging
                                        logging.warning(f"No se pudo eliminar archivo de cola {path_f}: {err}")
                                        
        detalles_cola = f" Archivos eliminados de la cola: {', '.join(archivos_eliminados)}." if archivos_eliminados else ""
        
        # Registrar auditoría
        log = LogAuditoria(
            usuario_id=usuario_id,
            orden_id=orden.id,
            accion="Cancelación de Orden",
            detalles=f"Orden #{orden.id} cancelada desde estado '{estado_anterior}'. Motivo: {motivo}.{detalles_saldo}{detalles_cola}"
        )
        session.add(log)
        session.commit()
        
        return jsonify({
            "mensaje": "Orden cancelada exitosamente",
            "orden_id": orden.id,
            "saldo_favor_actual": cliente.saldo_favor or 0.0
        }), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


