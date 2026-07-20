# ----------------------------------------------------------------------
# Copyright (c) 2026 Daniel Marin SysDev.
# Todos los derechos reservados.
# Este archivo es propiedad exclusiva de Daniel Marin.
# Queda prohibida su reproducción o distribución sin autorización.
# ----------------------------------------------------------------------
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Enum, Text, Float, Boolean
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import enum

Base = declarative_base()

# -------------------------------------------------------------------
# Enumeraciones para Roles y Estados
# -------------------------------------------------------------------
class RolEnum(enum.Enum):
    ADMIN = "Administrador"
    GERENCIA = "Gerencia"
    VENTAS = "Recepción / Soporte"
    DISENADOR = "Técnico de Diagnóstico"
    PRODUCCION = "Técnico de Reparación"
    INSTALADOR = "Técnico de Campo"

class EstadoOrdenEnum(enum.Enum):
    BORRADOR = "Borrador"
    PENDIENTE = "Pendiente (Ingreso)"
    EN_DISENO = "En Diagnóstico"
    EN_REVISION = "En Revisión (Presupuesto)"
    APROBADO_IMPRIMIR = "Reparación Aprobada"
    EN_PRODUCCION = "En Reparación / Servicio"
    LISTO_INSTALAR_ENTREGAR = "Listo para Entregar"
    COMPLETADO = "Completado / Entregado"
    CANCELADO = "Cancelado"

# -------------------------------------------------------------------
# Modelos de Base de Datos
# -------------------------------------------------------------------
class UsuarioRol(Base):
    """
    Tabla intermedia para soportar multi-roles (Relación Muchos a Muchos)
    """
    __tablename__ = 'usuario_roles'
    
    usuario_id = Column(Integer, ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True)
    rol = Column(Enum(RolEnum), primary_key=True)
    
    usuario = relationship("Usuario", back_populates="roles")

class Usuario(Base):
    """
    Tabla de usuarios con sus respectivos roles y permisos en el sistema.
    """
    __tablename__ = 'usuarios'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol_legacy = Column('rol', Enum(RolEnum), nullable=True)
    telefono = Column(String(50), nullable=True)
    
    roles = relationship("UsuarioRol", back_populates="usuario", cascade="all, delete-orphan")
    
    @property
    def rol(self):
        # Devuelve el rol de mayor jerarquía de la lista de roles del usuario
        if not self.roles:
            return RolEnum.INSTALADOR  # fallback
        roles_enums = [ur.rol for ur in self.roles]
        # Prioridad de mayor a menor jerarquía
        for r in [RolEnum.ADMIN, RolEnum.GERENCIA, RolEnum.VENTAS, RolEnum.DISENADOR, RolEnum.PRODUCCION, RolEnum.INSTALADOR]:
            if r in roles_enums:
                return r
        return roles_enums[0]
        
    @rol.setter
    def rol(self, nuevo_rol):
        if nuevo_rol:
            self.roles = [UsuarioRol(rol=nuevo_rol)]
            
    @property
    def roles_list(self):
        return [ur.rol for ur in self.roles]
        
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    ordenes_asignadas = relationship("OrdenTrabajo", back_populates="disenador")

class Pedido(Base):
    """
    Agrupador principal de uno o múltiples artículos (Órdenes de Trabajo).
    Representa una solicitud completa de un cliente.
    """
    __tablename__ = 'pedidos'
    
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.now)
    referencia = Column(String(100), nullable=True) # Nro factura, remito, etc.
    ruta_carpeta = Column(String(500), nullable=True) # D:\...\PEDIDO_123
    estado_pago = Column(String(50), default="Por Cancelar") # Por Cancelar, Abono, Cancelado
    monto_abono = Column(String(100), nullable=True) # Texto libre para abono
    metodo_pago = Column(String(100), nullable=True) # Pago Móvil, Zelle, Efectivo $, etc.
    monto_total = Column(Float, nullable=True)
    moneda = Column(String(10), default="USD")
    tasa_bcv = Column(Float, nullable=True)
    ocultar_precio_ventas = Column(Boolean, default=False, server_default="0")
    
    # Relaciones
    cliente = relationship("Cliente", back_populates="pedidos")
    articulos = relationship("OrdenTrabajo", back_populates="pedido", cascade="all, delete-orphan")

class Cliente(Base):
    """
    Tabla de clientes. Alberga la ruta base para la Master Data 
    (Activos Permanentes).
    """
    __tablename__ = 'clientes'
    
    id = Column(Integer, primary_key=True, autoincrement=True) # ID_CLIENTE
    nombre_empresa = Column(String(150), nullable=False)
    contacto_nombre = Column(String(150), nullable=True)
    email = Column(String(100), nullable=True)
    telefono = Column(String(50), nullable=True)
    
    # Ruta en el servidor: ej. [Disco]:\Clientes_Master\[ID_CLIENTE]_[Nombre]
    ruta_activos_permanentes = Column(String(500), nullable=True)
    saldo_favor = Column(Float, default=0.0)
    
    pedidos = relationship("Pedido", back_populates="cliente", cascade="all, delete-orphan")
    ordenes = relationship("OrdenTrabajo", back_populates="cliente", cascade="all, delete-orphan")

class OrdenTrabajo(Base):
    """
    Representa un artículo individual a fabricar dentro de un Pedido.
    """
    __tablename__ = 'ordenes_trabajo'
    
    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey('pedidos.id'), nullable=True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable=False)
    
    nombre_proyecto = Column(String(200), nullable=False)
    estado = Column(Enum(EstadoOrdenEnum), default=EstadoOrdenEnum.PENDIENTE)
    fecha_creacion = Column(DateTime, default=datetime.now)
    
    # Detalles técnicos
    especificaciones = Column(Text, nullable=True)
    diagnostico_defectos = Column(Text, nullable=True)
    diagnostico_detalles = Column(Text, nullable=True)
    diagnostico_insumos = Column(Text, nullable=True)
    diagnostico_observaciones = Column(Text, nullable=True)
    
    # Trazabilidad y Archivos Físicos
    ruta_archivos_transaccionales = Column(String(500), nullable=True)
    ruta_muestra = Column(String(500), nullable=True)
    ruta_instalacion = Column(String(500), nullable=True)
    
    # Asignación
    disenador_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    requiere_cotizacion = Column(Boolean, default=False, server_default="0")
    precio_unitario = Column(Float, nullable=True)
    
    # Relaciones
    pedido = relationship("Pedido", back_populates="articulos")
    cliente = relationship("Cliente", back_populates="ordenes")
    disenador = relationship("Usuario", back_populates="ordenes_asignadas")
    archivos = relationship("Archivo", back_populates="orden", cascade="all, delete-orphan")
    logs = relationship("LogAuditoria", back_populates="orden", cascade="all, delete-orphan")
    incidencias = relationship("Incidencia", back_populates="orden", cascade="all, delete-orphan")

    @property
    def precio_proporcional(self):
        """Monto total atribuible a esta tarjeta individual (OrdenTrabajo). Si existe precio_unitario específico se usa directamente."""
        if self.precio_unitario is not None and self.precio_unitario > 0:
            return float(self.precio_unitario)
        if not self.pedido or not self.pedido.monto_total:
            return 0.0
        num_articulos = len(self.pedido.articulos) if self.pedido.articulos else 1
        return self.pedido.monto_total / float(max(1, num_articulos))

    @property
    def abono_proporcional(self):
        """Abono registrado atribuible a esta tarjeta individual."""
        if not self.pedido or self.pedido.estado_pago == "Por Cancelar":
            return 0.0
        if self.pedido.estado_pago == "Cancelado":
            return self.precio_proporcional
        from routes_finanzas import extraer_monto_numerico
        abono_total = extraer_monto_numerico(self.pedido.monto_abono)
        num_articulos = len(self.pedido.articulos) if self.pedido.articulos else 1
        return abono_total / float(max(1, num_articulos))

    @property
    def saldo_pendiente_proporcional(self):
        """Saldo pendiente atribuible a esta tarjeta individual."""
        return max(0.0, self.precio_proporcional - self.abono_proporcional)

class Archivo(Base):
    """
    Tabla estructurada para la trazabilidad de archivos clave (opcional pero recomendada),
    como las "Pruebas de Ejecución" (fotos), o "Muestras" de diseño.
    """
    __tablename__ = 'archivos_adjuntos'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    orden_id = Column(Integer, ForeignKey('ordenes_trabajo.id'), nullable=False)
    subido_por_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True)
    
    nombre_archivo = Column(String(255), nullable=False)
    ruta_relativa = Column(String(500), nullable=False)
    
    # Para categorizar: MUESTRA_APROBACION, ARCHIVO_IMPRESION, PRUEBA_INSTALACION, etc.
    tipo_archivo = Column(String(100), nullable=False) 
    fecha_subida = Column(DateTime, default=datetime.now)
    
    orden = relationship("OrdenTrabajo", back_populates="archivos")

class LogAuditoria(Base):
    """
    Tabla para el registro de auditoría. Permite rastrear quién, cuándo y qué se modificó.
    """
    __tablename__ = 'logs_auditoria'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), nullable=True) # Quién realizó la acción
    orden_id = Column(Integer, ForeignKey('ordenes_trabajo.id'), nullable=True)
    accion = Column(String(255), nullable=False) # ej: "Cambio de Estado", "Orden Creada"
    detalles = Column(Text, nullable=True) # Detalles extra o contexto de la búsqueda/acción
    fecha = Column(DateTime, default=datetime.now)
    
    orden = relationship("OrdenTrabajo", back_populates="logs")

class PrecioMaterial(Base):
    """
    Tabla para configurar los precios de materiales por tipo de trabajo.
    Permite calcular cotizaciones en tiempo real.
    """
    __tablename__ = 'precios_materiales'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo_trabajo = Column(String(100), nullable=False) # ej: 'Sticker', 'Impresión', 'Impresión UV'
    material = Column(String(150), nullable=False) # ej: 'Vinil Matte', 'Banner 13oz', 'PVC Celular 3mm'
    precio_m2 = Column(Float, default=0.0) # Precio base por m2
    precio_laminado_m2 = Column(Float, default=0.0) # Adicional por m2 de laminado (deprecated, now stored as rows)
    es_adicional = Column(Boolean, default=False, server_default="0")

class Incidencia(Base):
    """
    Registro de incidencias, fallas o falta de insumos en planta de producción.
    """
    __tablename__ = 'incidencias'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reportado_por_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    orden_id = Column(Integer, ForeignKey('ordenes_trabajo.id'), nullable=True)
    tipo_problema = Column(String(100), nullable=False) # e.g. "Falta Material", "Falla de Máquina", "Retraso"
    detalles = Column(Text, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.now)
    estado = Column(String(50), default="Pendiente") # "Pendiente", "Resuelto"
    
    reportado_por = relationship("Usuario")
    orden = relationship("OrdenTrabajo", back_populates="incidencias")

class Configuracion(Base):
    """
    Configuraciones globales del sistema.
    """
    __tablename__ = 'configuraciones'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    clave = Column(String(100), unique=True, nullable=False) # ej: 'tipo_redondeo'
    valor = Column(String(255), nullable=False) # ej: 'exacto', 'entero_superior', 'decimal_cercano'


# -------------------------------------------------------------------
# Configuración y creación de la BD
# -------------------------------------------------------------------
# Utilizamos SQLite para la fase 1 de despliegue rápido, según el documento.
import os
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sistema_gestion_produccion.db")
engine = create_engine(DATABASE_URL, echo=True)

def init_db():
    """
    Crea todas las tablas definidas previamente en la base de datos SQLite.
    """
    Base.metadata.create_all(engine)
    
    # Parchear enum en Postgres si es necesario
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TYPE estadoordenenum ADD VALUE IF NOT EXISTS 'CANCELADO'"))
        print("Enum estadoordenenum parcheado con 'CANCELADO'")
    except Exception as ex:
        print(f"Aviso al parchear enum (probablemente ya existe o no es PostgreSQL): {ex}")
        
    # Parchear columna es_adicional si no existe
    try:
        with engine.begin() as conn:
            if "postgresql" in str(engine.url):
                conn.execute(text("ALTER TABLE precios_materiales ADD COLUMN IF NOT EXISTS es_adicional BOOLEAN DEFAULT FALSE"))
            else:
                conn.execute(text("ALTER TABLE precios_materiales ADD COLUMN es_adicional BOOLEAN DEFAULT FALSE"))
        print("Columna es_adicional agregada o verificada exitosamente.")
    except Exception as ex:
        print(f"Aviso al agregar columna es_adicional (probablemente ya existe): {ex}")
        
    # Parchear columnas de diagnóstico en ordenes_trabajo si no existen
    for col_name in ["diagnostico_defectos", "diagnostico_detalles", "diagnostico_insumos", "diagnostico_observaciones", "precio_unitario"]:
        try:
            with engine.begin() as conn:
                tipo_col = "FLOAT" if col_name == "precio_unitario" else "TEXT"
                if "postgresql" in str(engine.url):
                    conn.execute(text(f"ALTER TABLE ordenes_trabajo ADD COLUMN IF NOT EXISTS {col_name} {tipo_col}"))
                else:
                    conn.execute(text(f"ALTER TABLE ordenes_trabajo ADD COLUMN {col_name} {tipo_col}"))
            print(f"Columna {col_name} agregada o verificada exitosamente.")
        except Exception as ex:
            print(f"Aviso al agregar columna {col_name} (probablemente ya existe): {ex}")
            
    # Auto-migrar roles existentes a la tabla intermedia usuario_roles
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        usuarios = session.query(Usuario).all()
        for u in usuarios:
            if not u.roles:
                val_rol = getattr(u, 'rol_legacy', None)
                if val_rol:
                    if isinstance(val_rol, RolEnum):
                        nuevo_rol = UsuarioRol(usuario_id=u.id, rol=val_rol)
                        session.add(nuevo_rol)
                    elif isinstance(val_rol, str):
                        for r in RolEnum:
                            if r.value == val_rol or r.name == val_rol:
                                nuevo_rol = UsuarioRol(usuario_id=u.id, rol=r)
                                session.add(nuevo_rol)
                                break
        session.commit()
        print("Migración de roles de usuario legacy completada con éxito.")
    except Exception as migration_e:
        session.rollback()
        print(f"Aviso durante la migración de roles: {migration_e}")
    finally:
        session.close()
        
    print("¡Base de datos y tablas creadas exitosamente!")

if __name__ == "__main__":
    init_db()
