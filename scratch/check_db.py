from database_models import engine, OrdenTrabajo, Pedido, Cliente
from sqlalchemy.orm import sessionmaker
import datetime

Session = sessionmaker(bind=engine)
session = Session()
try:
    print("--- PEDIDOS ---")
    pedidos = session.query(Pedido).all()
    for p in pedidos:
        print(f"ID: {p.id}, Ref: {p.referencia}, Total: {p.monto_total}, Moneda: {p.moneda}, Pago: {p.estado_pago}, Abono: {p.monto_abono}, Metodo: {p.metodo_pago}")
        
    print("\n--- ORDENES DE TRABAJO ---")
    ordenes = session.query(OrdenTrabajo).all()
    for o in ordenes:
        print(f"ID: {o.id}, Pedido ID: {o.pedido_id}, Cliente: {o.cliente.nombre_empresa if o.cliente else 'N/A'}, Proyecto: {o.nombre_proyecto}, Estado: {o.estado.value}, Cotizacion: {o.requiere_cotizacion}")
finally:
    session.close()
