# ----------------------------------------------------------------------
# Copyright (c) 2026 Daniel Marin SysDev.
# Todos los derechos reservados.
# Este archivo es propiedad exclusiva de Daniel Marin.
# Queda prohibida su reproducción o distribución sin autorización.
# ----------------------------------------------------------------------
from flask import Blueprint, render_template, request, jsonify
import re
import datetime
from sqlalchemy import extract
from database_models import engine, Cliente, Pedido, LogAuditoria, OrdenTrabajo, RolEnum, Usuario, EstadoOrdenEnum
from routes_auth import login_required, role_required
from sqlalchemy.orm import sessionmaker
from utils_bcv import get_tasa_bcv

finanzas_bp = Blueprint('finanzas', __name__)
Session = sessionmaker(bind=engine)

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

@finanzas_bp.route('/finanzas/cuentas-por-cobrar', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def cuentas_cobrar_vista():
    return render_template('finanzas.html')

@finanzas_bp.route('/api/finanzas/deudores', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def obtener_deudores():
    session = Session()
    try:
        from flask import session as flask_session
        usuario_rol = flask_session.get('usuario_rol')
        rol_restringido = usuario_rol in [RolEnum.VENTAS.value, RolEnum.DISENADOR.value, RolEnum.INSTALADOR.value]

        # Obtener todos los clientes que tienen al menos un pedido Por Cancelar o Abono
        clientes = session.query(Cliente).all()
        deudores = []
        for c in clientes:
            pedidos_pendientes = session.query(Pedido).filter(
                Pedido.cliente_id == c.id,
                Pedido.estado_pago.in_(["Por Cancelar", "Abono"])
            ).all()
            
            if pedidos_pendientes:
                total_deuda_usd = 0.0
                total_deuda_bs = 0.0
                cliente_ocultar = False
                for p in pedidos_pendientes:
                    if p.ocultar_precio_ventas and rol_restringido:
                        cliente_ocultar = True
                    if p.estado_pago == "Por Cancelar":
                        saldo_p = float(p.monto_total or 0.0)
                    elif p.estado_pago == "Abono":
                        abono_val = extraer_monto_numerico(p.monto_abono)
                        saldo_p = max(0.0, float(p.monto_total or 0.0) - abono_val)
                    else:
                        saldo_p = 0.0
                        
                    if p.moneda == 'USD':
                        total_deuda_usd += saldo_p
                    elif p.moneda == 'Bs':
                        total_deuda_bs += saldo_p
                        
                deudores.append({
                    "id": c.id,
                    "nombre_empresa": c.nombre_empresa,
                    "contacto_nombre": c.contacto_nombre,
                    "telefono": c.telefono,
                    "cantidad_pedidos": len(pedidos_pendientes),
                    "total_usd": round(total_deuda_usd, 2) if not cliente_ocultar else None,
                    "total_bs": round(total_deuda_bs, 2) if not cliente_ocultar else None,
                    "ocultar_precio": cliente_ocultar
                })
                
        return jsonify(deudores), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@finanzas_bp.route('/api/finanzas/deudores/<int:cliente_id>/pedidos', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def obtener_pedidos_deudor(cliente_id):
    session = Session()
    try:
        from flask import session as flask_session
        usuario_rol = flask_session.get('usuario_rol')
        rol_restringido = usuario_rol in [RolEnum.VENTAS.value, RolEnum.DISENADOR.value, RolEnum.INSTALADOR.value]

        pedidos = session.query(Pedido).filter(
            Pedido.cliente_id == cliente_id,
            Pedido.estado_pago.in_(["Por Cancelar", "Abono"])
        ).order_by(Pedido.fecha_creacion.desc()).all()
        
        resultado = []
        for p in pedidos:
            ocultar = p.ocultar_precio_ventas and rol_restringido
            if p.estado_pago == "Por Cancelar":
                abono_num = 0.0
            else: # Es "Abono"
                abono_num = extraer_monto_numerico(p.monto_abono)
            total_num = float(p.monto_total or 0.0)
            resultado.append({
                "id": p.id,
                "referencia": p.referencia,
                "fecha": p.fecha_creacion.strftime('%d/%m/%Y'),
                "estado_pago": p.estado_pago,
                "monto_total": total_num if not ocultar else None,
                "moneda": p.moneda,
                "tasa_bcv": p.tasa_bcv if not ocultar else None,
                "monto_abono": p.monto_abono if not ocultar else "Oculto",
                "monto_abono_valor": abono_num if not ocultar else None,
                "resta_por_pagar": max(0.0, total_num - abono_num) if not ocultar else None,
                "ocultar_precio": ocultar
            })
            
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@finanzas_bp.route('/api/finanzas/pagar', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def registrar_pago():
    data = request.json
    if not data or 'pedidos' not in data:
        return jsonify({"error": "Datos inválidos"}), 400
        
    pedidos_ids = data.get('pedidos', []) # Lista de IDs de pedidos a liquidar
    detalles_pago = data.get('detalles', '') # Texto libre sobre el pago (Zelle, Efectivo, etc)
    metodo_pago = data.get('metodo_pago', '')
    
    if not pedidos_ids:
        return jsonify({"error": "No se seleccionaron pedidos"}), 400
        
    session = Session()
    try:
        pedidos = session.query(Pedido).filter(Pedido.id.in_(pedidos_ids)).all()
        
        # Agrupar notificaciones por teléfono para enviarlas en un único mensaje
        from collections import defaultdict
        notificaciones_agrupadas = defaultdict(lambda: {
            "nombre": "",
            "proyectos_list": [],
            "monto_total": 0.0
        })
        
        for p in pedidos:
            p.estado_pago = "Cancelado"
            p.monto_abono = f"Pagado. {detalles_pago}" if detalles_pago else "Pagado en su totalidad."
            p.metodo_pago = metodo_pago
            
            from flask import session as flask_session
            usuario_id_actual = flask_session.get('usuario_id', 1)
            # Log de auditoría por cada artículo en el pedido
            for art in p.articulos:
                log = LogAuditoria(
                    usuario_id=usuario_id_actual, 
                    orden_id=art.id,
                    accion="Liquidación de Pago",
                    detalles=f"Se liquidó el pedido {p.referencia}. Notas: {detalles_pago}"
                )
                session.add(log)
            
            if p.cliente and p.cliente.telefono:
                telefono = p.cliente.telefono
                nombre = p.cliente.contacto_nombre or p.cliente.nombre_empresa
                proyectos = ", ".join([art.nombre_proyecto for art in p.articulos])
                monto = p.monto_total if p.monto_total else 0.0
                
                notificaciones_agrupadas[telefono]["nombre"] = nombre
                notificaciones_agrupadas[telefono]["proyectos_list"].append(f"\"{proyectos}\" ({p.referencia})")
                notificaciones_agrupadas[telefono]["monto_total"] += monto
            
        session.commit()
        
        # Notificaciones de WhatsApp removidas en TaskCore
                
        return jsonify({"mensaje": f"Se registraron pagos para {len(pedidos)} pedidos"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@finanzas_bp.route('/api/finanzas/abonar', methods=['POST'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def registrar_abono():
    data = request.json
    if not data or 'pedido_id' not in data or 'monto' not in data:
        return jsonify({"error": "Datos inválidos"}), 400
        
    pedido_id = data.get('pedido_id')
    try:
        monto_nuevo = float(data.get('monto'))
    except ValueError:
        return jsonify({"error": "Monto inválido"}), 400
        
    detalles = data.get('detalles', '')
    metodo_pago = data.get('metodo_pago', '')
    
    session = Session()
    try:
        pedido = session.query(Pedido).filter_by(id=pedido_id).first()
        if not pedido:
            return jsonify({"error": "Pedido no encontrado"}), 404
            
        abono_anterior = pedido.monto_abono or "0"
        
        # Calcular el valor numérico total del abono
        val_abono_ant = extraer_monto_numerico(abono_anterior)
            
        val_abono_nuevo = val_abono_ant + monto_nuevo
        
        # Validar si el abono total cubre o supera el total del pedido
        monto_total = pedido.monto_total or 0.0
        detalles_str = f" ({detalles})" if detalles else ""
        
        # Formatear el token de abono con método estructurado para métricas
        token_nuevo = f"{monto_nuevo:.2f} [{metodo_pago or 'No especificado'}]"
        if detalles:
            token_nuevo += f" ({detalles})"
            
        if val_abono_nuevo >= monto_total:
            pedido.estado_pago = "Cancelado"
            exceso = val_abono_nuevo - monto_total
            if exceso > 0 and pedido.cliente:
                pedido.cliente.saldo_favor = (pedido.cliente.saldo_favor or 0.0) + exceso
                pedido.monto_abono = f"Abono total: {val_abono_nuevo:.2f}. Detalles: {abono_anterior} + Abonó {token_nuevo} (exceso de {exceso:.2f} guardado a favor)"
            else:
                pedido.monto_abono = f"Abono total: {val_abono_nuevo:.2f}. Detalles: {abono_anterior} + Abonó {token_nuevo} (Cancelado)"
        else:
            pedido.estado_pago = "Abono"
            resta = max(0.0, float(monto_total) - val_abono_nuevo)
            if val_abono_ant > 0:
                pedido.monto_abono = f"Abono total: {val_abono_nuevo:.2f}. Detalles: {abono_anterior} + Abonó {token_nuevo}. Resta por pagar: {resta:.2f}"
            else:
                pedido.monto_abono = f"Abonado {token_nuevo}. Resta por pagar: {resta:.2f}"
            
        pedido.metodo_pago = metodo_pago
        
        # Log de auditoría por cada artículo en el pedido
        from flask import session as flask_session
        usuario_id_actual = flask_session.get('usuario_id', 1)
        for art in pedido.articulos:
            log = LogAuditoria(
                usuario_id=usuario_id_actual,
                orden_id=art.id,
                accion="Registro de Abono",
                detalles=f"Se registró un abono de {monto_nuevo:.2f} en pedido {pedido.referencia}. Notas: {detalles}"
            )
            session.add(log)
        session.commit()
        
        # Notificación de abono por WhatsApp removida en TaskCore
                
        return jsonify({"mensaje": f"Se registró el abono de {monto_nuevo:.2f} exitosamente"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

def obtener_total_usd(pedido):
    if not pedido or not pedido.monto_total:
        return 0.0
    if pedido.moneda == 'Bs':
        tasa = pedido.tasa_bcv
        if not tasa or tasa <= 0:
            try:
                tasa = get_tasa_bcv() or 36.0
            except Exception:
                tasa = 36.0
        return pedido.monto_total / tasa
    return pedido.monto_total

def parsear_nombre_proyecto(nombre):
    nombre_limpio = re.sub(r'^\[\d+x\]\s*', '', nombre).strip()
    tipos_conocidos = [
        "Computadora / Laptop", "Celular / Smartphone", "Tablet", 
        "Servidor / Redes", "Consola de Videojuegos", "Otro",
        "Sticker", "Impresión y Corte", "Impresión UV", "Impresión", 
        "Banner", "Corte Vinil", "Corte Acrílico", "Corpórea"
    ]
    tipo_trabajo = "Otro"
    material = "N/A"
    
    for t in tipos_conocidos:
        if nombre_limpio.startswith(t):
            tipo_trabajo = t
            resto = nombre_limpio[len(t):].strip()
            if resto.startswith('-'):
                resto = resto[1:].strip()
            
            material_clean = re.sub(r'\s*\([^)]*\)', '', resto).strip()
            material_clean = material_clean.replace('+ Laminado', '').strip()
            if material_clean:
                material = material_clean
            break
            
    if tipo_trabajo == "Otro" and "-" in nombre_limpio:
        partes = nombre_limpio.split("-", 1)
        tipo_trabajo = partes[0].strip()
        material_clean = re.sub(r'\s*\([^)]*\)', '', partes[1]).strip()
        material_clean = material_clean.replace('+ Laminado', '').strip()
        material = material_clean if material_clean else "N/A"
        
    return tipo_trabajo, material

def calcular_area_de_medidas(tipo_trabajo, medidas_texto):
    if not medidas_texto:
        return 0.0
    medidas_texto = medidas_texto.lower().strip()
    if tipo_trabajo == 'Sticker':
        partes = medidas_texto.split()
        if partes:
            try:
                val_str = partes[0]
                if '/' in val_str:
                    num, den = val_str.split('/')
                    return float(num) / float(den)
                return float(val_str)
            except ValueError:
                pass
        return 1.0
    else:
        try:
            unidad = 'cm'
            if 'cm' in medidas_texto:
                medidas_texto = medidas_texto.replace('cm', '')
                unidad = 'cm'
            elif 'mm' in medidas_texto:
                medidas_texto = medidas_texto.replace('mm', '')
                unidad = 'mm'
            elif 'm' in medidas_texto:
                medidas_texto = medidas_texto.replace('m', '')
                unidad = 'm'
                
            if 'x' in medidas_texto:
                partes = medidas_texto.split('x')
                w = float(partes[0].strip())
                h = float(partes[1].strip())
                if w > 0 and h > 0:
                    if unidad == 'cm':
                        w /= 100.0
                        h /= 100.0
                    elif unidad == 'mm':
                        w /= 1000.0
                        h /= 1000.0
                    return w * h
        except Exception:
            pass
    return 0.0

@finanzas_bp.route('/finanzas/reportes', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def reportes_vista():
    return render_template('reportes.html')

@finanzas_bp.route('/api/finanzas/reportes', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def api_reportes():
    session = Session()
    try:
        mes_raw = request.args.get('mes')
        anio_raw = request.args.get('anio')
        
        hoy = datetime.date.today()
        anio = int(anio_raw) if anio_raw else hoy.year
        
        filtrar_por_mes = True
        if not mes_raw or mes_raw == 'todo' or mes_raw == '0' or mes_raw == '':
            filtrar_por_mes = False
            mes = 0
        else:
            try:
                mes = int(mes_raw)
            except ValueError:
                filtrar_por_mes = False
                mes = 0
                
        if filtrar_por_mes:
            if mes == 1:
                prev_mes = 12
                prev_anio = anio - 1
            else:
                prev_mes = mes - 1
                prev_anio = anio
                
            # Consultar Pedidos del mes
            pedidos_mes = session.query(Pedido).filter(
                extract('month', Pedido.fecha_creacion) == mes,
                extract('year', Pedido.fecha_creacion) == anio
            ).all()
            
            # Consultar Pedidos del mes anterior
            pedidos_prev = session.query(Pedido).filter(
                extract('month', Pedido.fecha_creacion) == prev_mes,
                extract('year', Pedido.fecha_creacion) == prev_anio
            ).all()
            
            # Consultar Órdenes de trabajo del mes (excluyendo borradores)
            ordenes_mes = session.query(OrdenTrabajo).join(Cliente).filter(
                extract('month', OrdenTrabajo.fecha_creacion) == mes,
                extract('year', OrdenTrabajo.fecha_creacion) == anio,
                OrdenTrabajo.estado != EstadoOrdenEnum.BORRADOR
            ).all()
        else:
            # Consultar Pedidos del año completo
            pedidos_mes = session.query(Pedido).filter(
                extract('year', Pedido.fecha_creacion) == anio
            ).all()
            
            # Consultar Pedidos del año anterior completo (para comparación YoY)
            pedidos_prev = session.query(Pedido).filter(
                extract('year', Pedido.fecha_creacion) == (anio - 1)
            ).all()
            
            # Consultar Órdenes de trabajo del año completo (excluyendo borradores)
            ordenes_mes = session.query(OrdenTrabajo).join(Cliente).filter(
                extract('year', OrdenTrabajo.fecha_creacion) == anio,
                OrdenTrabajo.estado != EstadoOrdenEnum.BORRADOR
            ).all()
        
        # Filtrar pedidos para excluir los que solo tienen artículos en revisión o borrador
        pedidos_mes = [p for p in pedidos_mes if any(o.estado not in [EstadoOrdenEnum.BORRADOR, EstadoOrdenEnum.EN_REVISION] for o in p.articulos)]
        pedidos_prev = [p for p in pedidos_prev if any(o.estado not in [EstadoOrdenEnum.BORRADOR, EstadoOrdenEnum.EN_REVISION] for o in p.articulos)]
        
        total_generado_mes = sum([obtener_total_usd(p) for p in pedidos_mes])
        total_generado_prev = sum([obtener_total_usd(p) for p in pedidos_prev])
        
        por_tipo = {}
        por_material = {}
        detalles_ordenes = []
        
        for o in ordenes_mes:
            tipo_trabajo, material = parsear_nombre_proyecto(o.nombre_proyecto)
            
            # Extraer cantidad
            cant_match = re.match(r'^\[(\d+)x\]', o.nombre_proyecto)
            cantidad = int(cant_match.group(1)) if cant_match else 1
            
            # Calcular ingreso de este artículo individual
            monto_usd = 0.0
            if o.pedido:
                total_ped_usd = obtener_total_usd(o.pedido)
                num_arts = len(o.pedido.articulos) if o.pedido.articulos else 1
                monto_usd = total_ped_usd / num_arts
            
            # Agrupar por tipo
            if tipo_trabajo not in por_tipo:
                por_tipo[tipo_trabajo] = {"cantidad": 0, "ingresos_usd": 0.0}
            por_tipo[tipo_trabajo]["cantidad"] += cantidad
            por_tipo[tipo_trabajo]["ingresos_usd"] += monto_usd
            
            # Agrupar por material
            if material != "N/A":
                if material not in por_material:
                    por_material[material] = {"cantidad": 0, "ingresos_usd": 0.0}
                por_material[material]["cantidad"] += cantidad
                por_material[material]["ingresos_usd"] += monto_usd
                
            ref_str = o.pedido.referencia if o.pedido else f"JOB-{o.id}"
            detalles_ordenes.append({
                "id": o.id,
                "nombre_proyecto": o.nombre_proyecto,
                "cliente": o.cliente.nombre_empresa,
                "fecha": o.fecha_creacion.strftime('%d/%m/%Y'),
                "estado": o.estado.value,
                "referencia": ref_str,
                "monto_pedido_usd": round(monto_usd, 2)
            })
            
        # 1. Rendimiento de Diseñadores
        disenadores_stats = {}
        disenadores = session.query(Usuario).filter(Usuario.rol == RolEnum.DISENADOR).all()
        for d in disenadores:
            disenadores_stats[d.nombre] = {
                "completados": 0,
                "en_progreso": 0,
                "total": 0
            }
            
        for o in ordenes_mes:
            if o.disenador:
                d_nombre = o.disenador.nombre
                if d_nombre not in disenadores_stats:
                    disenadores_stats[d_nombre] = {"completados": 0, "en_progreso": 0, "total": 0}
                
                disenadores_stats[d_nombre]["total"] += 1
                if o.estado in [EstadoOrdenEnum.COMPLETADO, EstadoOrdenEnum.LISTO_INSTALAR_ENTREGAR]:
                    disenadores_stats[d_nombre]["completados"] += 1
                else:
                    disenadores_stats[d_nombre]["en_progreso"] += 1

        # 2. Top Clientes (Calculado a nivel de Pedidos únicos para evitar duplicar montos y conteo)
        clientes_stats = {}
        for p in pedidos_mes:
            c_nombre = p.cliente.nombre_empresa
            if c_nombre not in clientes_stats:
                clientes_stats[c_nombre] = {
                    "pedidos_count": 0,
                    "total_usd": 0.0
                }
            clientes_stats[c_nombre]["pedidos_count"] += 1
            clientes_stats[c_nombre]["total_usd"] += obtener_total_usd(p)
            
        top_clientes = []
        for name, stats in clientes_stats.items():
            top_clientes.append({
                "cliente": name,
                "pedidos_count": stats["pedidos_count"],
                "total_usd": round(stats["total_usd"], 2)
            })
        top_clientes.sort(key=lambda x: x["total_usd"], reverse=True)
        top_clientes = top_clientes[:5]

        # 3. Estado de cobros
        cobros_stats = {
            "cobrado": 0.0,
            "abonos": 0.0,
            "pendiente": 0.0
        }
        for p in pedidos_mes:
            monto_usd = obtener_total_usd(p)
            if p.estado_pago == "Cancelado":
                cobros_stats["cobrado"] += monto_usd
            elif p.estado_pago == "Abono":
                abono_val = extraer_monto_numerico(p.monto_abono)
                if p.moneda == 'Bs':
                    tasa = p.tasa_bcv or 36.0
                    abono_usd = abono_val / tasa if tasa > 0 else 0.0
                else:
                    abono_usd = abono_val
                
                cobros_stats["abonos"] += abono_usd
                cobros_stats["pendiente"] += max(0.0, monto_usd - abono_usd)
            else: # Por Cancelar
                cobros_stats["pendiente"] += monto_usd
                
        cobros_stats["cobrado"] = round(cobros_stats["cobrado"], 2)
        cobros_stats["abonos"] = round(cobros_stats["abonos"], 2)
        cobros_stats["pendiente"] = round(cobros_stats["pendiente"], 2)

        # Obtener la tasa diaria oficial de BCV
        try:
            tasa_bcv_dia = get_tasa_bcv() or 36.0
        except Exception:
            tasa_bcv_dia = 36.0

        # 4. Desglose por métodos de pago
        metodos_estandar = [
            "Efectivo $",
            "Pago Móvil / Transferencia",
            "Zelle",
            "Efectivo Bs",
            "Saldo a favor",
            "Otro"
        ]
        desglose_pagos = {met: {"usd_eq": 0.0, "original_usd": 0.0, "original_bs": 0.0} for met in metodos_estandar}
        
        def normalizar_metodo(metodo_raw):
            if not metodo_raw:
                return "Otro"
            met = str(metodo_raw).strip().lower()
            if "pago" in met or "movil" in met or "móvil" in met or "transf" in met or "transferencia" in met:
                return "Pago Móvil / Transferencia"
            if "efectivo" in met and ("$" in met or "usd" in met or "dolar" in met or "dólar" in met):
                return "Efectivo $"
            if "efectivo" in met and ("bs" in met or "ves" in met or "boliv" in met):
                return "Efectivo Bs"
            if "zelle" in met:
                return "Zelle"
            if "saldo" in met or "favor" in met:
                return "Saldo a favor"
            if "efectivo" in met:
                return "Efectivo $"
            return "Otro"

        for p in pedidos_mes:
            if p.estado_pago in ["Cancelado", "Abono"]:
                # Intentar buscar los tokens detallados en el historial de abono
                matches = re.findall(r"([\d\.]+)\s*\[([^\]]+)\]", p.monto_abono or "")
                
                # Si no hay tokens detallados en el historial de abono, usar fallback
                if not matches:
                    if p.estado_pago == "Cancelado":
                        val_monto = float(p.monto_total or 0.0)
                    else:
                        val_monto = extraer_monto_numerico(p.monto_abono)
                    matches = [(str(val_monto), p.metodo_pago or "Otro")]
                
                for val_str, metodo_raw in matches:
                    try:
                        monto_original = float(val_str)
                    except ValueError:
                        continue
                        
                    metodo = normalizar_metodo(metodo_raw)
                    if metodo not in desglose_pagos:
                        desglose_pagos[metodo] = {"usd_eq": 0.0, "original_usd": 0.0, "original_bs": 0.0}
                        
                    tasa = p.tasa_bcv
                    if not tasa or tasa <= 0:
                        tasa = tasa_bcv_dia
                        
                    es_metodo_bs = metodo in ["Pago Móvil / Transferencia", "Efectivo Bs"]
                    es_metodo_usd = metodo in ["Zelle", "Efectivo $"]
                    
                    if p.moneda == 'Bs':
                        monto_bs = monto_original
                        monto_usd = monto_bs / tasa if tasa > 0 else 0.0
                    else:
                        monto_usd = monto_original
                        monto_bs = monto_usd * tasa
                        
                    desglose_pagos[metodo]["usd_eq"] += monto_usd
                    if es_metodo_bs:
                        desglose_pagos[metodo]["original_bs"] += monto_bs
                    elif es_metodo_usd:
                        desglose_pagos[metodo]["original_usd"] += monto_usd
                    else:
                        if p.moneda == 'Bs':
                            desglose_pagos[metodo]["original_bs"] += monto_bs
                        else:
                            desglose_pagos[metodo]["original_usd"] += monto_usd

        desglose_list = []
        for met in metodos_estandar:
            val = desglose_pagos.get(met, {"usd_eq": 0.0, "original_usd": 0.0, "original_bs": 0.0})
            desglose_list.append({
                "metodo": met,
                "usd_eq": round(val["usd_eq"], 2),
                "original_usd": round(val["original_usd"], 2),
                "original_bs": round(val["original_bs"], 2)
            })
        
        for met, val in desglose_pagos.items():
            if met not in metodos_estandar:
                desglose_list.append({
                    "metodo": met,
                    "usd_eq": round(val["usd_eq"], 2),
                    "original_usd": round(val["original_usd"], 2),
                    "original_bs": round(val["original_bs"], 2)
                })

        crecimiento = 0.0
        if total_generado_prev > 0:
            crecimiento = ((total_generado_mes - total_generado_prev) / total_generado_prev) * 100
            
        # Redondear ingresos a 2 decimales para la visualización
        for k in por_tipo:
            por_tipo[k]["ingresos_usd"] = round(por_tipo[k]["ingresos_usd"], 2)
        for k in por_material:
            por_material[k]["ingresos_usd"] = round(por_material[k]["ingresos_usd"], 2)
            
        # Obtener la tasa diaria oficial de BCV
        try:
            tasa_bcv_dia = get_tasa_bcv() or 36.0
        except Exception:
            tasa_bcv_dia = 36.0

        # Agrupar y contar las órdenes de trabajo del mes por estado (excluyendo BORRADOR)
        estados_count = {est.value: 0 for est in EstadoOrdenEnum if est != EstadoOrdenEnum.BORRADOR}
        for o in ordenes_mes:
            if o.estado.value in estados_count:
                estados_count[o.estado.value] += 1
                
        data = {
            "total_generado_mes": round(total_generado_mes, 2),
            "total_generado_prev": round(total_generado_prev, 2),
            "crecimiento_porcentaje": round(crecimiento, 2),
            "por_tipo": por_tipo,
            "por_material": por_material,
            "ordenes": detalles_ordenes,
            "disenadores": disenadores_stats,
            "top_clientes": top_clientes,
            "cobros_stats": cobros_stats,
            "desglose_pagos": desglose_list,
            "tasa_bcv_dia": tasa_bcv_dia,
            "total_ordenes_mes": len(ordenes_mes),
            "ordenes_por_estado": estados_count
        }
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@finanzas_bp.route('/api/finanzas/orden/<int:orden_id>/detalle', methods=['GET'])
@login_required
@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)
def get_orden_detalle(orden_id):
    session = Session()
    try:
        o = session.query(OrdenTrabajo).filter_by(id=orden_id).first()
        if not o:
            return jsonify({"error": "Orden no encontrada"}), 404
            
        logs_o = session.query(LogAuditoria).filter_by(orden_id=o.id).order_by(LogAuditoria.fecha.asc()).all()
        
        # Calcular duración del artículo actual
        def calcular_duracion_orden(ord_obj, logs_list):
            fecha_fin = None
            for l in logs_list:
                detalles_lower = (l.detalles or "").lower()
                accion_lower = (l.accion or "").lower()
                if "listo" in detalles_lower or "completado" in detalles_lower or "listo" in accion_lower or "completado" in accion_lower:
                    fecha_fin = l.fecha
                    break
            if not fecha_fin:
                if ord_obj.estado in [EstadoOrdenEnum.LISTO_INSTALAR_ENTREGAR, EstadoOrdenEnum.COMPLETADO]:
                    return "No registrado (Completado)"
                else:
                    tiempo = (datetime.datetime.now() - ord_obj.fecha_creacion).total_seconds() / 3600.0
                    return f"{int(tiempo // 24)}d {int(tiempo % 24)}h (En progreso)"
            diff = fecha_fin - ord_obj.fecha_creacion
            dias = diff.days
            horas = diff.seconds // 3600
            minutos = (diff.seconds % 3600) // 60
            if dias > 0:
                return f"{dias}d {horas}h {minutos}m"
            return f"{horas}h {minutos}m"
            
        duracion_actual = calcular_duracion_orden(o, logs_o)
        
        # Obtener información del Pedido y otros artículos
        pedido_info = None
        otros_articulos = []
        cronologia_pagos = []
        
        if o.pedido:
            p = o.pedido
            pedido_info = {
                "id": p.id,
                "referencia": p.referencia or f"REF-{p.id}",
                "monto_total": p.monto_total or 0.0,
                "moneda": p.moneda,
                "tasa_bcv": p.tasa_bcv,
                "estado_pago": p.estado_pago,
                "metodo_pago": p.metodo_pago or "No especificado",
                "monto_abono": p.monto_abono or "Ninguno"
            }
            
            # Obtener cronología de pagos
            art_ids = [art.id for art in p.articulos]
            pago_logs = session.query(LogAuditoria).filter(
                LogAuditoria.orden_id.in_(art_ids),
                (LogAuditoria.accion.like("%Abono%") | LogAuditoria.accion.like("%Pago%") | LogAuditoria.detalles.like("%Abon%"))
            ).order_by(LogAuditoria.fecha.asc()).all()
            
            cronologia_pagos.append({
                "fecha": p.fecha_creacion.strftime('%d/%m/%Y %I:%M %p'),
                "accion": "Creación de Pedido",
                "detalles": f"Pedido creado con monto total de ${p.monto_total:.2f} {p.moneda}. Estado: {p.estado_pago}."
            })
            
            for pl in pago_logs:
                cronologia_pagos.append({
                    "fecha": pl.fecha.strftime('%d/%m/%Y %I:%M %p'),
                    "accion": pl.accion,
                    "detalles": pl.detalles
                })
                
            # Otros artículos en el mismo pedido
            for art in p.articulos:
                logs_art = session.query(LogAuditoria).filter_by(orden_id=art.id).order_by(LogAuditoria.fecha.asc()).all()
                otros_articulos.append({
                    "id": art.id,
                    "nombre_proyecto": art.nombre_proyecto,
                    "estado": art.estado.value,
                    "duracion": calcular_duracion_orden(art, logs_art)
                })
        else:
            # Caso huérfano (sin pedido)
            pedido_info = {
                "id": None,
                "referencia": f"JOB-{o.id}",
                "monto_total": 0.0,
                "moneda": "USD",
                "tasa_bcv": 36.0,
                "estado_pago": "Sin Pedido",
                "metodo_pago": "Ninguno",
                "monto_abono": "Ninguno"
            }
            otros_articulos = [{
                "id": o.id,
                "nombre_proyecto": o.nombre_proyecto,
                "estado": o.estado.value,
                "duracion": duracion_actual
            }]
            
        data = {
            "id": o.id,
            "nombre_proyecto": o.nombre_proyecto,
            "especificaciones": o.especificaciones or "Sin especificaciones",
            "estado": o.estado.value,
            "fecha_creacion": o.fecha_creacion.strftime('%d/%m/%Y %I:%M %p'),
            "disenador": o.disenador.nombre if o.disenador else "No asignado",
            "duracion": duracion_actual,
            "pedido": pedido_info,
            "articulos": otros_articulos,
            "cronologia_pagos": cronologia_pagos,
            "diagnostico_defectos": o.diagnostico_defectos or "",
            "diagnostico_detalles": o.diagnostico_detalles or "",
            "diagnostico_insumos": o.diagnostico_insumos or "",
            "diagnostico_observaciones": o.diagnostico_observaciones or ""
        }
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
