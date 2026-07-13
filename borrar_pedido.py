import os
import sys
from dotenv import load_dotenv
load_dotenv()

from database_models import SessionLocal, Pedido

def main():
    if len(sys.argv) < 2:
        print("==========================================================")
        print("          UTILIDAD DE BORRADO DE PEDIDOS (GRAFI-K)")
        print("==========================================================")
        print("Uso: python borrar_pedido.py <id_del_pedido>")
        print("Ejemplo: python borrar_pedido.py 12")
        print("==========================================================")
        return

    try:
        pedido_id = int(sys.argv[1])
    except ValueError:
        print("[ERROR] El ID del pedido debe ser un numero entero.")
        return

    session = SessionLocal()
    try:
        pedido = session.query(Pedido).filter(Pedido.id == pedido_id).first()
        if not pedido:
            print(f"[ERROR] No se encontro ningun pedido con el ID: {pedido_id}")
            return
            
        print(f"\n[INFO] Se encontro el Pedido #{pedido.id}")
        print(f"  • Cliente ID: {pedido.cliente_id}")
        print(f"  • Referencia: {pedido.referencia or 'Sin referencia'}")
        print(f"  • Monto Total: ${pedido.monto_total or 0.0} USD")
        print(f"  • Cantidad de Articulos/Trabajos: {len(pedido.articulos)}")
        
        confirm = input("\n¿Estas seguro de que deseas borrar este pedido y TODOS sus articulos/logs asociados? (s/n): ")
        if confirm.lower() != 's':
            print("[INFO] Operacion cancelada.")
            return

        print("\n[OK] Borrando de la base de datos...")
        session.delete(pedido)
        session.commit()
        print("[OK] Pedido y todos sus registros relacionados borrados exitosamente.")
        
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Ocurrio un error al borrar el pedido: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    main()
