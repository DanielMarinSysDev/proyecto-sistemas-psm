from sqlalchemy import text
from database_models import engine, Usuario, RolEnum
from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)

def seed_users():
    session = Session()
    try:
        # Parchear enum en Postgres si es necesario
        try:
            session.execute(text("ALTER TYPE estadoordenenum ADD VALUE 'CANCELADO'"))
            session.commit()
            print("Enum estadoordenenum parcheado con 'CANCELADO'")
        except Exception as ex:
            session.rollback()
            print(f"Aviso al parchear enum (probablemente ya existe o no es PostgreSQL): {ex}")

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
            # Sticker
            PrecioMaterial(tipo_trabajo='Sticker', material='Vinil Brillante', precio_m2=12.0),
            PrecioMaterial(tipo_trabajo='Sticker', material='Vinil Brillante Blackout', precio_m2=13.0),
            PrecioMaterial(tipo_trabajo='Sticker', material='Vinil Matte', precio_m2=12.0),
            PrecioMaterial(tipo_trabajo='Sticker', material='Vinil Matte Blackout', precio_m2=13.0),
            PrecioMaterial(tipo_trabajo='Sticker', material='Vinil Transparente', precio_m2=14.0),
            PrecioMaterial(tipo_trabajo='Sticker', material='Vinil Transparente', precio_m2=5.0, es_adicional=True),
            
            # Impresión
            PrecioMaterial(tipo_trabajo='Impresión', material='Vinil Brillante', precio_m2=10.0),
            PrecioMaterial(tipo_trabajo='Impresión', material='Vinil Brillante Blackout', precio_m2=11.0),
            PrecioMaterial(tipo_trabajo='Impresión', material='Vinil Matte', precio_m2=10.0),
            PrecioMaterial(tipo_trabajo='Impresión', material='Vinil Matte Blackout', precio_m2=11.0),
            PrecioMaterial(tipo_trabajo='Impresión', material='Vinil Transparente', precio_m2=12.0),
            PrecioMaterial(tipo_trabajo='Impresión', material='Microperforado', precio_m2=15.0),
            PrecioMaterial(tipo_trabajo='Impresión', material='Vinil Transparente', precio_m2=5.0, es_adicional=True),
            
            # Impresión y Corte
            PrecioMaterial(tipo_trabajo='Impresión y Corte', material='Vinil Brillante', precio_m2=15.0),
            PrecioMaterial(tipo_trabajo='Impresión y Corte', material='Vinil Matte', precio_m2=15.0),
            PrecioMaterial(tipo_trabajo='Impresión y Corte', material='Vinil Transparente', precio_m2=17.0),
            PrecioMaterial(tipo_trabajo='Impresión y Corte', material='Vinil Transparente', precio_m2=5.0, es_adicional=True),
            
            # Impresión UV
            PrecioMaterial(tipo_trabajo='Impresión UV', material='PVC Celular', precio_m2=35.0),
            PrecioMaterial(tipo_trabajo='Impresión UV', material='Acrílico', precio_m2=65.0),
            PrecioMaterial(tipo_trabajo='Impresión UV', material='Coroplast', precio_m2=25.0),
            PrecioMaterial(tipo_trabajo='Impresión UV', material='MDF', precio_m2=30.0),
            PrecioMaterial(tipo_trabajo='Impresión UV', material='Vidrio', precio_m2=45.0),
            PrecioMaterial(tipo_trabajo='Impresión UV', material='Lona Banner UV', precio_m2=15.0),
            PrecioMaterial(tipo_trabajo='Impresión UV', material='Vinil UV', precio_m2=18.0),

            # Banner
            PrecioMaterial(tipo_trabajo='Banner', material='Lona Banner 13oz', precio_m2=10.0),
            PrecioMaterial(tipo_trabajo='Banner', material='Lona Banner 15oz', precio_m2=12.0),
            PrecioMaterial(tipo_trabajo='Banner', material='Lona Mesh', precio_m2=14.0),

            # Banner Finishes (Mapeados como es_adicional=True)
            PrecioMaterial(tipo_trabajo='Banner', material='Pendón Armado', precio_m2=2.0, es_adicional=True),
            PrecioMaterial(tipo_trabajo='Banner', material='Ojetes', precio_m2=1.0, es_adicional=True),
            PrecioMaterial(tipo_trabajo='Banner', material='Bastidor Madera', precio_m2=12.0, es_adicional=True),
            PrecioMaterial(tipo_trabajo='Banner', material='Bastidor Metal', precio_m2=20.0, es_adicional=True),

            # Corte Vinil
            PrecioMaterial(tipo_trabajo='Corte Vinil', material='Vinil Brillante', precio_m2=12.0),
            PrecioMaterial(tipo_trabajo='Corte Vinil', material='Vinil Brillante Blackout', precio_m2=13.0),
            PrecioMaterial(tipo_trabajo='Corte Vinil', material='Vinil Matte', precio_m2=12.0),
            PrecioMaterial(tipo_trabajo='Corte Vinil', material='Vinil Matte Blackout', precio_m2=13.0),
            PrecioMaterial(tipo_trabajo='Corte Vinil', material='Vinil Transparente', precio_m2=14.0),

            # Corte Acrílico
            PrecioMaterial(tipo_trabajo='Corte Acrílico', material='Acrílico 3mm', precio_m2=45.0),
            PrecioMaterial(tipo_trabajo='Corte Acrílico', material='Acrílico 5mm', precio_m2=60.0),
            PrecioMaterial(tipo_trabajo='Corte Acrílico', material='Acrílico 8mm', precio_m2=80.0),

            # Tablero PVC (Instalación, Mapeado como es_adicional=True)
            PrecioMaterial(tipo_trabajo='Tablero PVC', material='3mm', precio_m2=15.0, es_adicional=True),
            PrecioMaterial(tipo_trabajo='Tablero PVC', material='6mm', precio_m2=20.0, es_adicional=True),
            PrecioMaterial(tipo_trabajo='Tablero PVC', material='9mm', precio_m2=25.0, es_adicional=True),
            PrecioMaterial(tipo_trabajo='Tablero PVC', material='12mm', precio_m2=30.0, es_adicional=True),
            PrecioMaterial(tipo_trabajo='Tablero PVC', material='15mm', precio_m2=35.0, es_adicional=True),
            PrecioMaterial(tipo_trabajo='Tablero PVC', material='30mm', precio_m2=50.0, es_adicional=True),
            PrecioMaterial(tipo_trabajo='Tablero PVC', material='60mm', precio_m2=80.0, es_adicional=True)
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
