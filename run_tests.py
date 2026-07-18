import os
import sys
import unittest
import shutil
from datetime import datetime

# Agregar la ruta del workspace
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(WORKSPACE_DIR)

# Configurar base de datos de pruebas aislada y API Key de mentira para el test del Agente IA
os.environ["DATABASE_URL"] = "sqlite:///sistema_gestion_produccion_test.db"
os.environ["GEMINI_API_KEY"] = "mock-api-key-for-testing"
os.environ["TESTING"] = "true"

# Definir base de archivos de prueba adaptable a Windows y Linux (CI)
if os.name == 'nt' and os.path.exists("D:\\"):
    TEST_BASE_DIR = r"D:\TaskCore_Archivos_Test"
else:
    TEST_BASE_DIR = os.path.join(WORKSPACE_DIR, "TaskCore_Archivos_Test")

os.environ["BASE_DIR"] = TEST_BASE_DIR

from app import app
from database_models import Base, engine, Usuario, Cliente, Pedido, OrdenTrabajo, RolEnum, EstadoOrdenEnum
from sqlalchemy.orm import sessionmaker

# Configurar sesión local de BD
Session = sessionmaker(bind=engine)

DB_FILE = os.path.join(WORKSPACE_DIR, "sistema_gestion_produccion_test.db")

class TestSistemaTaskCore(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        print("\n--- CONFIGURANDO EL ENTORNO DE PRUEBAS ---")
        if os.path.exists(DB_FILE):
            try:
                os.remove(DB_FILE)
            except Exception:
                pass
            
        # 2. Inicializar base de datos limpia
        print("Creando base de datos limpia para pruebas...")
        Base.metadata.create_all(engine)
        
        # 3. Sembrar datos necesarios para pruebas (Usuarios y Clientes)
        cls.db_session = Session()
        try:
            # Crear Usuarios de Prueba para cada Rol
            cls.u_admin = Usuario(nombre="Admin Test", email="admin@taskcore.com", rol=RolEnum.ADMIN)
            cls.u_admin.set_password("admin123")
            
            cls.u_ventas = Usuario(nombre="Ventas Test", email="ventas@taskcore.com", rol=RolEnum.VENTAS)
            cls.u_ventas.set_password("ventas123")
            
            cls.u_diseno = Usuario(nombre="Diseno Test", email="diseno@taskcore.com", rol=RolEnum.DISENADOR)
            cls.u_diseno.set_password("diseno123")
            
            cls.u_prod = Usuario(nombre="Prod Test", email="prod@taskcore.com", rol=RolEnum.PRODUCCION)
            cls.u_prod.set_password("prod123")
            
            cls.db_session.add_all([cls.u_admin, cls.u_ventas, cls.u_diseno, cls.u_prod])
            
            # Crear Cliente de Prueba
            # Ruta de activos permanentes: D:\TaskCore_Archivos_Test\Clientes_Master\1_Cliente_Prueba\Activos_Permanentes
            client_master_path = os.path.join(TEST_BASE_DIR, "Clientes_Master", "1_Cliente_Prueba", "Activos_Permanentes")
            os.makedirs(client_master_path, exist_ok=True)
            
            cls.cliente = Cliente(
                nombre_empresa="Cliente Prueba",
                contacto_nombre="Juan Perez",
                email="juan@perez.com",
                telefono="0412-1234567",
                ruta_activos_permanentes=client_master_path
            )
            cls.db_session.add(cls.cliente)
            cls.db_session.commit()
            print("Datos de prueba sembrados exitosamente.")
            
            # Sembrar precios de materiales de prueba
            from seed import seed_prices
            seed_prices()
        except Exception as e:
            cls.db_session.rollback()
            print(f"Error sembrando datos: {e}")
            raise e
        finally:
            cls.db_session.close()
            
        # Configurar cliente de pruebas de Flask
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key'
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        print("\n--- DESHABILITANDO EL ENTORNO DE PRUEBAS ---")
        # Liberar conexiones activas de SQLAlchemy para evitar bloqueos de archivo SQLite
        engine.dispose()
        
        # 1. Remover base de datos temporal
        if os.path.exists(DB_FILE):
            try:
                os.remove(DB_FILE)
            except Exception:
                pass
            
        # 3. Limpiar archivos y carpetas temporales generados en D:\TaskCore_Archivos_Test
        if os.path.exists(TEST_BASE_DIR):
            try:
                print(f"Limpiando directorio de archivos temporales en {TEST_BASE_DIR}...")
                shutil.rmtree(TEST_BASE_DIR)
            except Exception as e:
                print(f"Aviso: No se pudo eliminar completamente {TEST_BASE_DIR}: {e}")

    def login(self, email, password):
        return self.client.post(
            '/api/login',
            json={'email': email, 'password': password}
        )

    def logout(self):
        return self.client.post('/api/logout')

    # =================================================================
    # 1. PRUEBAS DE AUTENTICACIÓN
    # =================================================================
    def test_01_login_exitoso(self):
        """Probar inicio de sesión correcto."""
        resp = self.login("admin@taskcore.com", "admin123")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("mensaje", data)
        self.assertEqual(data["usuario"]["rol"], "Administrador")
        self.logout()

    def test_02_login_incorrecto(self):
        """Probar inicio de sesión fallido con contraseña incorrecta."""
        resp = self.login("admin@taskcore.com", "clave_incorrecta")
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn("error", data)

    # =================================================================
    # 2. PRUEBAS DE RBAC (ROLES Y ACCESOS)
    # =================================================================
    def test_03_acceso_anonimo_denegado(self):
        """Verificar que rutas protegidas nieguen acceso anónimo (redirección a login o 401)."""
        # Intentar acceder a panel de usuarios
        resp = self.client.get('/usuarios')
        self.assertEqual(resp.status_code, 401)

    def test_04_acceso_usuario_no_admin(self):
        """Verificar que endpoints de administrador nieguen acceso a Ventas (403)."""
        # Iniciar sesión como Ventas
        self.login("ventas@taskcore.com", "ventas123")
        
        # Intentar acceder a listado de usuarios (Solo Admin)
        resp = self.client.get('/usuarios')
        self.assertEqual(resp.status_code, 403)
        self.logout()

    # =================================================================
    # 3. PRUEBAS DE CREACIÓN DE ÓRDENES Y VALIDACIÓN DE PARÁMETROS
    # =================================================================
    def test_05_creacion_pedido_faltan_campos(self):
        """Probar que falten campos devuelva Bad Request (400)."""
        self.login("ventas@taskcore.com", "ventas123")
        resp = self.client.post('/api/ordenes', json={})
        self.assertEqual(resp.status_code, 400)
        self.logout()

    def test_06_creacion_orden_computadora(self):
        """Verificar la creación correcta de una orden de Computadora con su nombre concatenado."""
        self.login("ventas@taskcore.com", "ventas123")
        
        resp = self.client.post(
            '/api/ordenes',
            json={
                'cliente_id': 1,
                'creador_id': 2,
                'referencia': 'REF-COMP-01',
                'estado_pago': 'Cancelado',
                'monto_total': 15.0,
                'moneda': 'USD',
                'tasa_bcv': 36.5,
                'articulos': [
                    {
                        'tipo_trabajo': 'Computadora / Laptop',
                        'material': 'Diagnóstico Técnico General',
                        'cantidad': 1,
                        'specs': 'No enciende la pantalla'
                    }
                ]
            }
        )
        self.assertEqual(resp.status_code, 201)
        
        # Verificar la orden en BD
        db_session = Session()
        try:
            orden = db_session.query(OrdenTrabajo).filter(OrdenTrabajo.nombre_proyecto.like("%Computadora%")).first()
            self.assertIsNotNone(orden)
            
            # Nombre final del proyecto
            self.assertEqual(orden.nombre_proyecto, "Computadora / Laptop - Diagnóstico Técnico General")
            # Especificaciones
            self.assertEqual(orden.especificaciones, "No enciende la pantalla")
            
            # Verificar carpetas creadas en disco (Esquema simplificado de 3 carpetas)
            self.assertTrue(os.path.exists(orden.ruta_archivos_transaccionales))
            self.assertTrue(os.path.exists(os.path.join(orden.ruta_archivos_transaccionales, "Diagnostico_Firmware")))
            self.assertTrue(os.path.exists(os.path.join(orden.ruta_archivos_transaccionales, "Entregables_Reportes")))
            self.assertTrue(os.path.exists(os.path.join(orden.ruta_archivos_transaccionales, "Evidencia_Fotos")))
            
            # El symlink directo debe estar en la raíz de la carpeta del artículo
            symlink_txt = os.path.join(orden.ruta_archivos_transaccionales, "LEER_Activos_Permanentes.txt")
            symlink_real = os.path.join(orden.ruta_archivos_transaccionales, "ACCESO_DIRECTO_Activos_Permanentes")
            self.assertTrue(os.path.exists(symlink_txt) or os.path.exists(symlink_real))
            
        finally:
            db_session.close()
        self.logout()

    def test_07_creacion_orden_celular_cantidad(self):
        """Verificar que una orden de Celular con cantidad preserve la cantidad en el nombre."""
        self.login("ventas@taskcore.com", "ventas123")
        
        resp = self.client.post(
            '/api/ordenes',
            json={
                'cliente_id': 1,
                'creador_id': 2,
                'referencia': 'REF-CEL-01',
                'estado_pago': 'Por Cancelar',
                'monto_total': 70.0,
                'moneda': 'USD',
                'tasa_bcv': 36.5,
                'articulos': [
                    {
                        'tipo_trabajo': 'Celular / Smartphone',
                        'material': 'Cambio de Batería',
                        'cantidad': 2,
                        'specs': 'Baterías infladas'
                    }
                ]
            }
        )
        self.assertEqual(resp.status_code, 201)
        
        # Verificar la orden en BD
        db_session = Session()
        try:
            orden = db_session.query(OrdenTrabajo).filter(OrdenTrabajo.nombre_proyecto.like("%Celular%")).first()
            self.assertIsNotNone(orden)
            
            # Nombre final del proyecto
            self.assertEqual(orden.nombre_proyecto, "[2x] Celular / Smartphone - Cambio de Batería")
            
        finally:
            db_session.close()
        self.logout()

    # =================================================================
    # 4. PRUEBA DE TRANSICIONES, ARCHIVADO DE EDITABLES Y HOT FOLDERS
    # =================================================================
    def test_08_aprobacion_orden_y_vinculaciones(self):
        """Probar que aprobar orden genere los enlaces duros de editables y salida de impresión."""
        self.login("diseno@taskcore.com", "diseno123")
        
        db_session = Session()
        try:
            orden = db_session.query(OrdenTrabajo).filter(OrdenTrabajo.nombre_proyecto.like("%Celular / Smartphone%")).first()
            self.assertIsNotNone(orden)
            
            # Crear archivos mock en la orden antes de aprobarla
            editable_dir = os.path.join(orden.ruta_archivos_transaccionales, "Diagnostico_Firmware")
            salida_dir = os.path.join(orden.ruta_archivos_transaccionales, "Entregables_Reportes")
            
            mock_editable = os.path.join(editable_dir, "proyecto_vector.ai")
            mock_salida = os.path.join(salida_dir, "impresion_final.pdf")
            
            with open(mock_editable, "w") as f:
                f.write("editable mock data")
            with open(mock_salida, "w") as f:
                f.write("print mock data")
                
            # Cambiar estado a Reparación Aprobada
            resp = self.client.put(
                f'/api/ordenes/{orden.id}/estado',
                json={
                    'nuevo_estado': 'Reparación Aprobada',
                    'usuario_id': 3
                }
            )
            self.assertEqual(resp.status_code, 200)
            
            # 1. Verificar archivado automático de editable en la carpeta del cliente
            cliente = db_session.query(Cliente).first()
            client_files = os.listdir(cliente.ruta_activos_permanentes)
            
            # Debe existir un archivo que termine en proyecto_vector.ai y tenga el prefijo de la orden
            archived_editable = [f for f in client_files if "proyecto_vector.ai" in f]
            self.assertTrue(len(archived_editable) > 0)
            
            # 2. Verificar vinculación a Hot Folder (Debería ir a LABORATORIO_HARDWARE por ser "batería" en el nombre)
            hot_folder_root = os.path.join(TEST_BASE_DIR, "Cola_Soporte", "LABORATORIO_HARDWARE")
            self.assertTrue(os.path.exists(hot_folder_root))
            
            destino_dir = hot_folder_root
            self.assertTrue(os.path.exists(destino_dir))
            
            hot_files = os.listdir(destino_dir)
            archived_hot = [f for f in hot_files if "impresion_final.pdf" in f]
            self.assertTrue(len(archived_hot) > 0)
            
        finally:
            db_session.close()
        self.logout()

    # =================================================================
    # 5. PRUEBA DE SUBIDA DE ARCHIVOS (MUESTRAS / INSTALACIONES)
    # =================================================================
    def test_09_subida_muestras_e_instalacion(self):
        """Probar la subida de archivos JPG a la carpeta Muestras."""
        self.login("diseno@taskcore.com", "diseno123")
        
        db_session = Session()
        try:
            # Obtener la orden que sí tiene los archivos mock creados
            orden = db_session.query(OrdenTrabajo).filter(OrdenTrabajo.nombre_proyecto.like("%Celular / Smartphone%")).first()
            
            # Simular subida de muestra
            data = {
                'file': (open(os.path.join(orden.ruta_archivos_transaccionales, "Diagnostico_Firmware", "proyecto_vector.ai"), 'rb'), 'test_image.jpg')
            }
            
            resp = self.client.post(
                f'/api/ordenes/{orden.id}/upload-muestra',
                data=data,
                content_type='multipart/form-data'
            )
            self.assertEqual(resp.status_code, 200)
            
            # Verificar que el archivo se guardó físicamente en la subcarpeta "Muestras"
            muestras_dir = os.path.join(orden.ruta_archivos_transaccionales, "Evidencia_Fotos")
            self.assertTrue(os.path.exists(os.path.join(muestras_dir, "test_image.jpg")))
            
        finally:
            db_session.close()
        self.logout()

    # =================================================================
    # 6. PRUEBAS DE TARIFAS Y COTIZACIÓN EN VIVO
    # =================================================================
    def test_10_calculo_precios(self):
        """Probar el endpoint de cotización en vivo y cálculo dinámico."""
        self.login("ventas@taskcore.com", "ventas123")
        
        # Test 1: Diagnóstico de laptop (Tarifa base $15.0)
        resp = self.client.post(
            '/api/precios/calcular',
            json={
                'tipo_trabajo': 'Computadora / Laptop',
                'material': 'Diagnóstico Técnico General',
                'cantidad': 1
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["subtotal"], 15.0)
        self.assertEqual(data["area_m2"], 1.0)
        
        # Test 2: Cambio de batería de celular (Tarifa base $35.0 * 2)
        resp = self.client.post(
            '/api/precios/calcular',
            json={
                'tipo_trabajo': 'Celular / Smartphone',
                'material': 'Cambio de Batería',
                'cantidad': 2
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["subtotal"], 70.0) # 2 * $35.0
        
        self.logout()

    def test_11_administracion_precios_y_rbac(self):
        """Probar ABM de precios y protección de roles (RBAC)."""
        # 1. Ventas no debería poder agregar precios (403)
        self.login("ventas@taskcore.com", "ventas123")
        resp = self.client.post(
            '/api/precios',
            json={
                'tipo_trabajo': 'Computadora / Laptop',
                'material': 'Limpieza Avanzada',
                'precio_m2': 20.0
            }
        )
        self.assertEqual(resp.status_code, 403)
        self.logout()
        
        # 2. Admin sí puede agregar precios
        self.login("admin@taskcore.com", "admin123")
        resp = self.client.post(
            '/api/precios',
            json={
                'tipo_trabajo': 'Computadora / Laptop',
                'material': 'Limpieza Avanzada',
                'precio_m2': 20.0,
                'precio_laminado_m2': 0.0
            }
        )
        self.assertEqual(resp.status_code, 200)
        
        # Verificar que se insertó en BD
        db_session = Session()
        try:
            from database_models import PrecioMaterial
            tarifa = db_session.query(PrecioMaterial).filter_by(material='Limpieza Avanzada').first()
            self.assertIsNotNone(tarifa)
            self.assertEqual(tarifa.precio_m2, 20.0)
            
            # 3. Eliminar la tarifa
            resp = self.client.delete(f'/api/precios/{tarifa.id}')
            self.assertEqual(resp.status_code, 200)
            
            # Verificar eliminación
            tarifa_del = db_session.query(PrecioMaterial).filter_by(material='Limpieza Avanzada').first()
            self.assertIsNone(tarifa_del)
        finally:
            db_session.close()
            
        self.logout()

    def test_12_cotizacion_dispositivo_diferente(self):
        """Verifica que las cotizaciones para Tablet y Servidores se calculen correctamente."""
        self.login('admin@taskcore.com', 'admin123')
        
        # 1. Test Tablet
        resp = self.client.post('/api/precios/calcular', json={
            "tipo_trabajo": "Tablet",
            "material": "Cambio de Batería (Tablet)",
            "cantidad": 1
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['subtotal'], 40.0)

        # 2. Test Servidor / Redes
        resp = self.client.post('/api/precios/calcular', json={
            "tipo_trabajo": "Servidor / Redes",
            "material": "Configuración de Red / Firewall",
            "cantidad": 1
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['subtotal'], 80.0)

        self.logout()

    def test_13_politicas_redondeo(self):
        """
        Prueba la configuración y el impacto de las políticas globales de redondeo.
        """
        self.login('admin@taskcore.com', 'admin123')
        
        # Crear tarifas de prueba decimales
        self.client.post(
            '/api/precios',
            json={
                'tipo_trabajo': 'Computadora / Laptop',
                'material': 'Servicio Test Redondeo 1',
                'precio_m2': 15.60
            }
        )
        self.client.post(
            '/api/precios',
            json={
                'tipo_trabajo': 'Computadora / Laptop',
                'material': 'Servicio Test Redondeo 2',
                'precio_m2': 16.64
            }
        )
        
        payload_1 = {
            "tipo_trabajo": "Computadora / Laptop",
            "material": "Servicio Test Redondeo 1",
            "cantidad": 1
        }
        
        # 1. Redondeo: Exacto
        resp_set = self.client.post('/api/configuracion/redondeo', json={"valor": "exacto"})
        self.assertEqual(resp_set.status_code, 200)
        
        resp_calc = self.client.post('/api/precios/calcular', json=payload_1)
        self.assertEqual(resp_calc.get_json()['subtotal'], 15.60)
        
        # 2. Redondeo: Entero Superior (Ceil)
        resp_set = self.client.post('/api/configuracion/redondeo', json={"valor": "entero_superior"})
        self.assertEqual(resp_set.status_code, 200)
        
        resp_calc = self.client.post('/api/precios/calcular', json=payload_1)
        self.assertEqual(resp_calc.get_json()['subtotal'], 16.00)
        
        # 3. Redondeo: Decimal más cercano (.50)
        resp_set = self.client.post('/api/configuracion/redondeo', json={"valor": "decimal_cercano"})
        self.assertEqual(resp_set.status_code, 200)
        
        resp_calc = self.client.post('/api/precios/calcular', json=payload_1)
        self.assertEqual(resp_calc.get_json()['subtotal'], 15.50)
        
        # Probar otro valor: $16.64 -> redondeo a 16.50
        payload_2 = {
            "tipo_trabajo": "Computadora / Laptop",
            "material": "Servicio Test Redondeo 2",
            "cantidad": 1
        }
        resp_calc = self.client.post('/api/precios/calcular', json=payload_2)
        self.assertEqual(resp_calc.get_json()['subtotal'], 16.50)
        
        # Restaurar a exacto
        self.client.post('/api/configuracion/redondeo', json={"valor": "exacto"})
        
        # Limpiar BD
        db_session = Session()
        try:
            from database_models import PrecioMaterial
            db_session.query(PrecioMaterial).filter(PrecioMaterial.material.like("Servicio Test Redondeo%")).delete(synchronize_session=False)
            db_session.commit()
        finally:
            db_session.close()
            
        self.logout()

    def test_19_configuracion_intervalo_recordatorio(self):
        """
        Prueba obtener y guardar el intervalo de recordatorio de deudas.
        """
        self.login('admin@taskcore.com', 'admin123')
        
        # 1. Obtener por defecto (debería ser '3')
        resp_get = self.client.get('/api/configuracion/intervalo_recordatorio')
        self.assertEqual(resp_get.status_code, 200)
        self.assertEqual(resp_get.get_json()['valor'], '3')
        
        # 2. Guardar un nuevo valor
        resp_post = self.client.post('/api/configuracion/intervalo_recordatorio', json={"valor": "5"})
        self.assertEqual(resp_post.status_code, 200)
        
        # 3. Obtener el nuevo valor
        resp_get = self.client.get('/api/configuracion/intervalo_recordatorio')
        self.assertEqual(resp_get.status_code, 200)
        self.assertEqual(resp_get.get_json()['valor'], '5')
        
        # 4. Probar valor inválido
        resp_invalid = self.client.post('/api/configuracion/intervalo_recordatorio', json={"valor": "-1"})
        self.assertEqual(resp_invalid.status_code, 400)
        
        # 5. Probar no autorizado con rol no permitido (por ejemplo, ventas)
        self.logout()
        self.login('ventas@taskcore.com', 'ventas123')
        resp_unauth = self.client.post('/api/configuracion/intervalo_recordatorio', json={"valor": "7"})
        self.assertEqual(resp_unauth.status_code, 403)
        
        self.logout()

    def test_20_calculo_sin_dimensiones_default_area(self):
        """
        Prueba que si no se pasan dimensiones, el área m2 por defecto sea 1.0.
        """
        self.login('admin@taskcore.com', 'admin123')
        
        payload = {
            "tipo_trabajo": "Computadora / Laptop",
            "material": "Diagnóstico Técnico General",
            "cantidad": 1
        }
        resp = self.client.post('/api/precios/calcular', json=payload)
        self.assertEqual(resp.status_code, 200)
        
        data = resp.get_json()
        self.assertEqual(data['area_m2'], 1.0)
        self.assertEqual(data['subtotal'], 15.0)
        
        self.logout()

    def test_14_reportes_y_metricas(self):
        """
        Prueba el acceso y estructura del reporte de métricas e historial mensual.
        """
        # 1. Ventas no debería poder acceder (403)
        self.login('ventas@taskcore.com', 'ventas123')
        resp = self.client.get('/finanzas/reportes')
        self.assertEqual(resp.status_code, 403)
        resp_api = self.client.get('/api/finanzas/reportes')
        self.assertEqual(resp_api.status_code, 403)
        self.logout()
        
        # 2. Admin sí puede acceder
        self.login('admin@taskcore.com', 'admin123')
        resp = self.client.get('/finanzas/reportes')
        self.assertEqual(resp.status_code, 200)
        
        # 3. Validar estructura del API de reportes
        resp_api = self.client.get('/api/finanzas/reportes')
        self.assertEqual(resp_api.status_code, 200)
        data = resp_api.get_json()
        
        self.assertIn('total_generado_mes', data)
        self.assertIn('total_generado_prev', data)
        self.assertIn('crecimiento_porcentaje', data)
        self.assertIn('por_tipo', data)
        self.assertIn('por_material', data)
        self.assertIn('ordenes', data)
        self.assertIn('disenadores', data)
        self.assertIn('top_clientes', data)
        self.assertIn('cobros_stats', data)
        
        # 4. Validar reporte anual ("Todo el año")
        resp_anual = self.client.get('/api/finanzas/reportes?mes=todo&anio=2026')
        self.assertEqual(resp_anual.status_code, 200)
        data_anual = resp_anual.get_json()
        self.assertIn('total_generado_mes', data_anual)
        self.assertIn('cobros_stats', data_anual)
        
        self.logout()

    def test_15_edicion_usuario(self):
        """
        Prueba la modificación de usuarios a través de la ruta PUT.
        """
        # 1. Ventas no debería poder editar (403)
        self.login('ventas@taskcore.com', 'ventas123')
        resp = self.client.put('/api/usuarios/3', json={
            "nombre": "Nombre Editado",
            "email": "editado@taskcore.com",
            "rol": "Técnico de Diagnóstico"
        })
        self.assertEqual(resp.status_code, 403)
        self.logout()
        
        # 2. Admin sí puede editar
        self.login('admin@taskcore.com', 'admin123')
        resp = self.client.put('/api/usuarios/3', json={
            "nombre": "Diseno Test Modificado",
            "email": "diseno_mod@taskcore.com",
            "rol": "Técnico de Diagnóstico",
            "password": "nuevapassword123"
        })
        self.assertEqual(resp.status_code, 200)
        
        # Intentar editar con email duplicado de otro usuario (admin@taskcore.com)
        resp_dup = self.client.put('/api/usuarios/3', json={
            "nombre": "Diseno Test Modificado",
            "email": "admin@taskcore.com",
            "rol": "Técnico de Diagnóstico"
        })
        self.assertEqual(resp_dup.status_code, 400)
        
        self.logout()

    def test_18_reporte_incidencias(self):
        """
        Prueba el registro, listado y resolución de incidencias en producción.
        """
        # Iniciar sesión como Admin
        self.login('admin@taskcore.com', 'admin123')
        
        # 1. Reportar una incidencia
        resp = self.client.post('/api/ordenes/1/incidencias', json={
            "usuario_id": 1,
            "tipo_problema": "Falta Material",
            "detalles": "No queda pasta térmica en stock para este mantenimiento."
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("incidencia_id", data)
        incidencia_id = data["incidencia_id"]
        
        # 2. Listar incidencias de la orden 1
        resp_list = self.client.get('/api/ordenes/1/incidencias')
        self.assertEqual(resp_list.status_code, 200)
        lista = resp_list.get_json()
        self.assertTrue(len(lista) > 0)
        self.assertEqual(lista[0]["tipo_problema"], "Falta Material")
        self.assertEqual(lista[0]["estado"], "Pendiente")
        
        # 3. Resolver la incidencia
        resp_resolve = self.client.put(f'/api/incidencias/{incidencia_id}/resolver', json={
            "usuario_id": 1
        })
        self.assertEqual(resp_resolve.status_code, 200)
        
        # 4. Verificar estado resuelto
        resp_list2 = self.client.get('/api/ordenes/1/incidencias')
        lista2 = resp_list2.get_json()
        self.assertEqual(lista2[0]["estado"], "Resuelto")
            
        self.logout()

    def test_21_motivo_sin_costo(self):
        """Verificar que crear o confirmar una orden sin costo (monto_total <= 0) requiere un motivo."""
        self.login("ventas@taskcore.com", "ventas123")
        
        # 1. Intentar crear orden con monto_total = 0 y sin motivo -> Debe retornar 400
        resp = self.client.post(
            '/api/ordenes',
            json={
                'cliente_id': 1,
                'creador_id': 2,
                'referencia': 'REF-GRATIS-FAIL',
                'estado_pago': 'Cancelado',
                'monto_total': 0.0,
                'moneda': 'USD',
                'tasa_bcv': 36.5,
                'articulos': [
                    {
                        'tipo_trabajo': 'Computadora / Laptop',
                        'material': 'Diagnóstico Técnico General',
                        'cantidad': 1,
                        'specs': 'Prueba sin costo'
                    }
                ]
            }
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Para pedidos sin costo, debe especificar el motivo", resp.get_json().get("error", ""))
        
        # 2. Crear orden con monto_total = 0 y especificando motivo -> Debe retornar 201
        resp_ok = self.client.post(
            '/api/ordenes',
            json={
                'cliente_id': 1,
                'creador_id': 2,
                'referencia': 'REF-GRATIS-OK',
                'estado_pago': 'Cancelado',
                'monto_total': 0.0,
                'moneda': 'USD',
                'tasa_bcv': 36.5,
                'motivo_sin_costo': 'Garantía por error previo',
                'articulos': [
                    {
                        'tipo_trabajo': 'Computadora / Laptop',
                        'material': 'Diagnóstico Técnico General',
                        'cantidad': 1,
                        'specs': 'Prueba sin costo con motivo'
                    }
                ]
            }
        )
        self.assertEqual(resp_ok.status_code, 201)
        self.logout()

    def test_22_precio_minimo_configuracion_y_calculo(self):
        """
        Prueba configurar un precio mínimo por artículo y verificar que se aplique.
        """
        self.login('admin@taskcore.com', 'admin123')
        
        # 1. Configurar precio mínimo a $12.00 (Diagnóstico Celular base es $10.00)
        resp_set = self.client.post('/api/configuracion/precio_minimo', json={"valor": "12.00"})
        self.assertEqual(resp_set.status_code, 200)
        
        # 2. Calcular precio (base $10.00 < $12.00, con cantidad=2, el total debe ser $24.00)
        payload = {
            "tipo_trabajo": "Celular / Smartphone",
            "material": "Diagnóstico Técnico General",
            "cantidad": 2
        }
        resp_calc = self.client.post('/api/precios/calcular', json=payload)
        self.assertEqual(resp_calc.status_code, 200)
        data = resp_calc.get_json()
        self.assertEqual(data['subtotal'], 24.00) # $12.00 * 2
        
        # 3. Restaurar precio mínimo por defecto ($1.00)
        self.client.post('/api/configuracion/precio_minimo', json={"valor": "1.00"})
        self.logout()

    def test_23_seguridad_ocultar_monto_y_resolver_incidencias(self):
        """Verificar la seguridad de ocultar_precio_ventas y resolución de incidencias."""
        # 1. Ventas intenta crear con ocultar_precio_ventas = True
        self.login("ventas@taskcore.com", "ventas123")
        resp = self.client.post(
            '/api/ordenes',
            json={
                'cliente_id': 1,
                'creador_id': 2,
                'referencia': 'REF-OCULTAR-TEST',
                'estado_pago': 'Por Cancelar',
                'monto_total': 100.0,
                'moneda': 'USD',
                'tasa_bcv': 36.5,
                'ocultar_precio_ventas': True, # Debe ser ignorado (forzado a False)
                'articulos': [
                    {
                        'tipo_trabajo': 'Computadora / Laptop',
                        'material': 'Diagnóstico Técnico General',
                        'cantidad': 1,
                        'specs': 'Prueba seguridad'
                    }
                ]
            }
        )
        self.assertEqual(resp.status_code, 201)
        pedido_id = resp.get_json()["pedido_id"]
        
        # Verificar en base de datos que se guardó como False
        db_session = Session()
        try:
            pedido = db_session.query(Pedido).filter_by(id=pedido_id).first()
            self.assertIsNotNone(pedido)
            self.assertFalse(pedido.ocultar_precio_ventas)
        finally:
            db_session.close()
            
        # 2. Ventas intenta resolver una incidencia (debería dar 403)
        # Primero reportamos una incidencia como Ventas
        resp_inc = self.client.post('/api/ordenes/1/incidencias', json={
            "usuario_id": 2,
            "tipo_problema": "Fallo de Repuesto",
            "detalles": "Test seguridad"
        })
        self.assertEqual(resp_inc.status_code, 201)
        incidencia_id = resp_inc.get_json()["incidencia_id"]
        
        # Intentar resolver como Ventas -> 403
        resp_res_fail = self.client.put(f'/api/incidencias/{incidencia_id}/resolver', json={
            "usuario_id": 2
        })
        self.assertEqual(resp_res_fail.status_code, 403)
        self.logout()
        
        # 3. Admin intenta resolver la incidencia -> 200
        self.login("admin@taskcore.com", "admin123")
        resp_res_ok = self.client.put(f'/api/incidencias/{incidencia_id}/resolver', json={
            "usuario_id": 1
        })
        self.assertEqual(resp_res_ok.status_code, 200)
        self.logout()

    def test_24_gestion_usuarios_gerencia(self):
        """Verificar que Gerencia pueda gestionar usuarios de menor rango, pero no de rango igual o superior."""
        # 1. Crear usuario de Gerencia usando Admin
        self.login("admin@taskcore.com", "admin123")
        resp_crear_gerente = self.client.post('/api/usuarios', json={
            "nombre": "Gerente Test",
            "email": "gerente@taskcore.com",
            "password": "gerente123",
            "rol": "Gerencia",
            "telefono": "0412-1111111"
        })
        self.assertEqual(resp_crear_gerente.status_code, 201)
        self.logout()

        # 2. Iniciar sesión como Gerente
        self.login("gerente@taskcore.com", "gerente123")

        # 2a. Intentar crear usuario Administrador -> 403
        resp_fail_admin = self.client.post('/api/usuarios', json={
            "nombre": "Fail Admin",
            "email": "fail_admin@taskcore.com",
            "password": "adminpwd123",
            "rol": "Administrador"
        })
        self.assertEqual(resp_fail_admin.status_code, 403)

        # 2b. Intentar crear otro Gerente -> 403
        resp_fail_gerente = self.client.post('/api/usuarios', json={
            "nombre": "Fail Gerente",
            "email": "fail_gerente@taskcore.com",
            "password": "gerentepwd123",
            "rol": "Gerencia"
        })
        self.assertEqual(resp_fail_gerente.status_code, 403)

        # 2c. Crear usuario Ventas -> 201
        resp_ok_ventas = self.client.post('/api/usuarios', json={
            "nombre": "Vendedor Gerencia",
            "email": "vendedor_ger@taskcore.com",
            "password": "vendedor123",
            "rol": "Recepción / Soporte"
        })
        self.assertEqual(resp_ok_ventas.status_code, 201)

        # Buscar el ID del vendedor creado y del admin existente
        db_session = Session()
        try:
            vendedor = db_session.query(Usuario).filter_by(email="vendedor_ger@taskcore.com").first()
            self.assertIsNotNone(vendedor)
            vendedor_id = vendedor.id
            
            admin_user = db_session.query(Usuario).filter_by(email="admin@taskcore.com").first()
            self.assertIsNotNone(admin_user)
            admin_id = admin_user.id
        finally:
            db_session.close()

        # 2d. Intentar editar al Administrador -> 403
        resp_edit_admin = self.client.put(f'/api/usuarios/{admin_id}', json={
            "nombre": "Admin Editado",
            "email": "admin@taskcore.com",
            "rol": "Administrador"
        })
        self.assertEqual(resp_edit_admin.status_code, 403)

        # 2e. Editar al Vendedor -> 200
        resp_edit_vendedor = self.client.put(f'/api/usuarios/{vendedor_id}', json={
            "nombre": "Vendedor Modificado",
            "email": "vendedor_ger@taskcore.com",
            "rol": "Recepción / Soporte"
        })
        self.assertEqual(resp_edit_vendedor.status_code, 200)

        # 2f. Intentar cambiar rol del Vendedor a Administrador o Gerencia -> 403
        resp_edit_rol_admin = self.client.put(f'/api/usuarios/{vendedor_id}', json={
            "nombre": "Vendedor Modificado",
            "email": "vendedor_ger@taskcore.com",
            "rol": "Administrador"
        })
        self.assertEqual(resp_edit_rol_admin.status_code, 403)

        # 2g. Intentar eliminar al Administrador -> 403
        resp_del_admin = self.client.delete(f'/api/usuarios/{admin_id}')
        self.assertEqual(resp_del_admin.status_code, 403)

        # 2h. Eliminar al Vendedor -> 200
        resp_del_vendedor = self.client.delete(f'/api/usuarios/{vendedor_id}')
        self.assertEqual(resp_del_vendedor.status_code, 200)

        self.logout()

        # 3. Ventas intenta acceder a /usuarios -> 403
        self.login("ventas@taskcore.com", "ventas123")
        resp_vista = self.client.get('/usuarios')
        self.assertEqual(resp_vista.status_code, 403)
        self.logout()

    def test_25_seguridad_respaldos_y_mantenimiento(self):
        """
        Prueba la seguridad y validación de credenciales para la descarga y restauración de respaldos.
        """
        # 1. Acceso anónimo
        resp = self.client.post('/api/mantenimiento/restaurar', json={"filename": "test.sql", "password": "123"})
        self.assertIn(resp.status_code, [302, 401])

        # 2. Acceso como Recepción/Soporte (No Admin)
        self.login("ventas@taskcore.com", "ventas123")
        resp = self.client.post('/api/mantenimiento/restaurar', json={"filename": "test.sql", "password": "123"})
        self.assertEqual(resp.status_code, 403)
        self.logout()

        # 3. Acceso como Administrador
        self.login("admin@taskcore.com", "admin123")

        # 3a. Restaurar sin contraseña
        resp = self.client.post('/api/mantenimiento/restaurar', json={"filename": "test.sql"})
        self.assertEqual(resp.status_code, 401)

        # 3b. Restaurar con contraseña incorrecta
        resp = self.client.post('/api/mantenimiento/restaurar', json={"filename": "test.sql", "password": "wrongpassword"})
        self.assertEqual(resp.status_code, 401)

        # 3c. Descargar sin contraseña
        resp = self.client.post('/api/mantenimiento/respaldos/test.sql/descargar', json={})
        self.assertEqual(resp.status_code, 401)

        # 3d. Descargar con contraseña incorrecta
        resp = self.client.post('/api/mantenimiento/respaldos/test.sql/descargar', json={"password": "wrongpassword"})
        self.assertEqual(resp.status_code, 401)

        # 3e. Subir y restaurar sin contraseña
        resp = self.client.post('/api/mantenimiento/subir-restaurar', data={})
        self.assertEqual(resp.status_code, 401)

        # 3f. Subir y restaurar con contraseña incorrecta
        import io
        resp = self.client.post('/api/mantenimiento/subir-restaurar', data={
            "password": "wrongpassword",
            "file": (io.BytesIO(b"CREATE TABLE test;"), "test.sql")
        })
        self.assertEqual(resp.status_code, 401)

        # 3g. Subir y restaurar con contraseña correcta pero sin sello
        resp = self.client.post('/api/mantenimiento/subir-restaurar', data={
            "password": "admin123",
            "file": (io.BytesIO(b"CREATE TABLE test;"), "test.sql")
        })
        self.assertEqual(resp.status_code, 500)
        self.assertIn("no contiene un sello dinámico", resp.json.get("error", ""))

        # 3h. Subir y restaurar con contraseña correcta y sello modificado/incorrecto
        resp = self.client.post('/api/mantenimiento/subir-restaurar', data={
            "password": "admin123",
            "file": (io.BytesIO(b"CREATE TABLE test;\n-- FIRMA_AUTENTICIDAD_TASKCORE:wronghash"), "test.sql")
        })
        self.assertEqual(resp.status_code, 500)
        self.assertIn("El sello dinámico no coincide", resp.json.get("error", ""))

        # 3i. Subir y restaurar con contraseña correcta y sello correcto (docker no presente en test)
        import hmac
        import hashlib
        content = b"CREATE TABLE test;\n"
        # Obtener el SECRET_KEY igual a como lo hace restaurar_db.py
        secret_key_val = os.getenv("SECRET_KEY", "dev_key_temporal_secreta_12345")
        firma = hmac.new(secret_key_val.encode('utf-8'), content, hashlib.sha256).hexdigest()
        signed_file = content + f"-- FIRMA_AUTENTICIDAD_TASKCORE:{firma}\n".encode('utf-8')
        
        resp = self.client.post('/api/mantenimiento/subir-restaurar', data={
            "password": "admin123",
            "file": (io.BytesIO(signed_file), "test.sql")
        })
        self.assertEqual(resp.status_code, 500)
        self.assertNotIn("Error de Seguridad:", resp.json.get("error", ""))

        self.logout()

if __name__ == '__main__':
    unittest.main()
