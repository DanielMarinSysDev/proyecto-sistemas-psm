from sqlalchemy import text
from database_models import engine, Usuario, RolEnum
from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)

def seed_users():
    session = Session()
    try:
        # Parchear enum en Postgres si es necesario (ya ejecutado previamente)
        # try:
        #     session.execute(text("ALTER TYPE estadoordenenum ADD VALUE 'CANCELADO'"))
        #     session.commit()
        #     print("Enum estadoordenenum parcheado con 'CANCELADO'")
        # except Exception as ex:
        #     session.rollback()
        #     print(f"Aviso al parchear enum (probablemente ya existe o no es PostgreSQL): {ex}")

        # Verificar si ya existe el admin
        admin = session.query(Usuario).filter_by(email="admin@taskcore.com").first()
        if not admin:
            admin = Usuario(
                nombre="Administrador Principal",
                email="admin@taskcore.com",
                rol=RolEnum.ADMIN,
                telefono="+584120000001"
            )
            admin.set_password("admin123")
            session.add(admin)
            print("Usuario Admin creado: admin@taskcore.com / admin123")
            
        # Verificar si ya existe el vendedor
        ventas = session.query(Usuario).filter_by(email="ventas@taskcore.com").first()
        if not ventas:
            ventas = Usuario(
                nombre="Representante de Ventas",
                email="ventas@taskcore.com",
                rol=RolEnum.VENTAS,
                telefono="+584120000002"
            )
            ventas.set_password("ventas123")
            session.add(ventas)
            print("Usuario Ventas creado: ventas@taskcore.com / ventas123")
            
        session.commit()
        print("Base de datos inicializada con usuarios de prueba.")
        
    except Exception as e:
        session.rollback()
        print(f"Error insertando usuarios: {e}")
    finally:
        session.close()

def seed_prices():
    from database_models import PrecioMaterial
    session = Session()
    try:
        # Limpiar precios anteriores para sobreescribir con nombres alineados al formulario
        session.query(PrecioMaterial).delete()
        default_prices = [
            # Servicios Técnicos - Computadora / Laptop
            PrecioMaterial(tipo_trabajo='Computadora / Laptop', material='Diagnóstico Técnico General', precio_m2=15.0),
            PrecioMaterial(tipo_trabajo='Computadora / Laptop', material='Diagnóstico Express', precio_m2=25.0),
            PrecioMaterial(tipo_trabajo='Computadora / Laptop', material='Mantenimiento Preventivo (Limpieza)', precio_m2=20.0),
            PrecioMaterial(tipo_trabajo='Computadora / Laptop', material='Formateo y Reinstalación de SO', precio_m2=25.0),
            PrecioMaterial(tipo_trabajo='Computadora / Laptop', material='Respaldo de Información (hasta 1TB)', precio_m2=20.0),
            PrecioMaterial(tipo_trabajo='Computadora / Laptop', material='Instalación de SSD + Clonación', precio_m2=45.0),
            PrecioMaterial(tipo_trabajo='Computadora / Laptop', material='Reparación de Placa Madre (Nivel Componente)', precio_m2=75.0),
            PrecioMaterial(tipo_trabajo='Computadora / Laptop', material='Cambio de Pantalla LCD (Laptop)', precio_m2=90.0),

            # Servicios Técnicos - Celular / Smartphone
            PrecioMaterial(tipo_trabajo='Celular / Smartphone', material='Diagnóstico Técnico General', precio_m2=10.0),
            PrecioMaterial(tipo_trabajo='Celular / Smartphone', material='Cambio de Batería', precio_m2=35.0),
            PrecioMaterial(tipo_trabajo='Celular / Smartphone', material='Cambio de Pantalla LCD (Móvil)', precio_m2=50.0),
            PrecioMaterial(tipo_trabajo='Celular / Smartphone', material='Reparación de Puerto de Carga Pin', precio_m2=25.0),

            # Servicios Técnicos - Tablet
            PrecioMaterial(tipo_trabajo='Tablet', material='Diagnóstico Técnico General', precio_m2=12.0),
            PrecioMaterial(tipo_trabajo='Tablet', material='Cambio de Pantalla LCD (Tablet)', precio_m2=60.0),
            PrecioMaterial(tipo_trabajo='Tablet', material='Cambio de Batería (Tablet)', precio_m2=40.0),

            # Servicios Técnicos - Consola de Videojuegos
            PrecioMaterial(tipo_trabajo='Consola de Videojuegos', material='Limpieza Física Interna (Consola)', precio_m2=30.0),
            PrecioMaterial(tipo_trabajo='Consola de Videojuegos', material='Rebalanceo Térmico / Cambio de Pasta', precio_m2=35.0),

            # Servicios Técnicos - Servidor / Redes
            PrecioMaterial(tipo_trabajo='Servidor / Redes', material='Mantenimiento Físico y Lógico', precio_m2=120.0),
            PrecioMaterial(tipo_trabajo='Servidor / Redes', material='Configuración de Red / Firewall', precio_m2=80.0),

            # Servicios Técnicos - Otro
            PrecioMaterial(tipo_trabajo='Otro', material='Diagnóstico Técnico General', precio_m2=15.0),
            PrecioMaterial(tipo_trabajo='Otro', material='Servicio Técnico Técnico Especializado', precio_m2=40.0)
        ]
        session.add_all(default_prices)
        
        # Sembrar configuración de redondeo por defecto
        from database_models import Configuracion
        # Borrar configuración anterior para evitar duplicaciones
        session.query(Configuracion).filter_by(clave='tipo_redondeo').delete()
        config = Configuracion(clave='tipo_redondeo', valor='exacto')
        session.add(config)
        
        # Restaurar nombre de asesor humano por defecto
        session.query(Configuracion).filter_by(clave='nombre_asesor_responsable').delete()
        config_asesor = Configuracion(clave='nombre_asesor_responsable', valor='un asesor de ventas')
        session.add(config_asesor)
        
        session.commit()
        print("Precios de materiales y configuración sembrados exitosamente.")
    except Exception as e:
        session.rollback()
        print(f"Error sembrando precios: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    seed_users()
    seed_prices()
