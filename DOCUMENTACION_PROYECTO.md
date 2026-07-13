# Sistema de Gestión de Producción TaskCore

## Contexto del Proyecto
Desarrollo de un sistema de gestión de flujo de trabajo (Workflow Management System) tipo Intranet para una agencia de diseño gráfico e impresión. El sistema centraliza la gestión de órdenes, el estado de los diseños, y la organización inteligente de archivos en un servidor local para evitar la redundancia de datos.

## 1. Pila Tecnológica Sugerida (Tech Stack)
* **Backend**: Python (Framework Flask).
* **Base de Datos**: PostgreSQL (para desarrollo y producción en Docker) y soporte heredado para SQLite mediante SQLAlchemy.
* **Frontend**: HTML5, CSS3 con diseño personalizado (Vanilla CSS, Glassmorphism).
* **Manejo de Archivos**: Interacción directa con el sistema de archivos (OS) para gestionar enlaces simbólicos, enlaces duros y directorios compartidos en red.
* **Contenedores**: Docker y Docker Compose para aislar el motor web y la base de datos PostgreSQL.

## 2. Estado Actual del Proyecto (Implementado)
El sistema se encuentra en un estado funcional completo y maduro con las siguientes características implementadas:
* **Backend y Base de Datos**: 
  * Aplicación Flask configurada y modularizada (`app.py`).
  * Base de datos PostgreSQL en contenedor Docker (`taskcore_db`) con persistencia local mapeada por volumen.
  * Modelos de SQLAlchemy actualizados (`database_models.py`): `Usuario`, `Cliente`, `Pedido`, `OrdenTrabajo`, `Archivo`, `LogAuditoria`, `PrecioMaterial`, e `Incidencia`.
  * Migraciones y control de versiones de esquema automatizado mediante **Alembic**.
* **Gestión de Borradores**:
  * Panel de gestión de borradores (`/recepcion/borradores`) para editar, aprobar (confirmar) o rechazar propuestas creadas o cargadas manualmente.
* **Control de Precios, Tarifas y Cotizaciones Especiales**:
  * Casilla de *"Cotización Especial"* al crear o confirmar pedidos. Al activarse, levanta una **Incidencia de tipo "Cotización Especial"** que bloquea el flujo del trabajo en el Kanban.
  * **Excepción de Laminado para Vinil Transparente**: Desactivación interactiva en el frontend y anulación automática del costo de laminación en el backend (evaluado a `$0.00`) para materiales transparentes/microperforados, previniendo cobros duplicados.
  * **Acabados Dinámicos de Banner**: Los acabados y adicionales de banner (como ojetes, pendones armados o bastidores) se gestionan como adicionales en la base de datos (`es_adicional=True`), eliminando listas estáticas y dropdowns anidados.
  * **Semaforización Visual**: En la administración de tarifas, badges semáforo diferencian con colores de alto contraste los *Materiales Base* de los *Acabados y Adicionales*.
  * Resolución de presupuesto directamente desde el Kanban (por Admin/Gerencia) con opción de ocultar el precio al personal de Ventas/Recepción.
* **Seguridad de Precios y Roles**:
  * Implementación de la propiedad `ocultar_precio_ventas` en pedidos.
  * Censura automática de importes monetarios y desgloses de abono en los endpoints del backend para roles limitados (Ventas, Diseñador, Producción, Instalador).
  * Renderizado seguro en el frontend que muestra `[RESERVADO]` en lugar de importes financieros.
* **Diseño y Apariencia**:
  * Estética Premium con Glassmorphism, paleta corporativa azul (#0278D2), y soporte nativo para **Tema Claro** y **Tema Oscuro** con persistencia local.
  * Favicon corporativo y logotipos vectoriales dinámicos configurados.
  * PWA 100% instalable con manifiesto de aplicación y variaciones del logotipo en azul, blanco y negro.

## 3. Roles de Usuario y Permisos (RBAC)
* **Administrador**: Acceso ilimitado. Puede crear, editar y eliminar cualquier usuario de cualquier rol en el sistema, resolver incidencias (incluyendo cotizaciones especiales), fijar precios de cotizaciones manuales, ocultar/mostrar precios (toggling the `ocultar_precio_ventas` option) y realizar mantenimiento del sistema (respaldos y restauraciones).
* **Gerencia**: Acceso a reportes financieros y resolución/aprobación de cotizaciones especiales. Comparte con el Administrador el permiso de configurar la visibilidad de los precios (`ocultar_precio_ventas`). También tiene permiso para gestionar (crear, editar y eliminar) cuentas de usuario, restringido estrictamente a roles por debajo de ellos (no puede crear, modificar ni eliminar otros Gerentes o Administradores).
* **Ventas / Recepción**: Crea y confirma órdenes o borradores. No puede resolver incidencias ni cotizaciones especiales, ni tiene la facultad de activar la opción "Ocultar Precio a Ventas" (tanto la interfaz como el backend restringen esta acción). Si un administrador o gerente oculta los precios de un pedido, el vendedor verá la información financiera restringida como `[RESERVADO]`.
* **Diseñador / Operador / Instalador**: Acceso limitado a las tareas operativas de su área; no tienen visibilidad de los datos monetarios ni funciones administrativas.

## 4. Secuencia de Procesos (Flujo de Trabajo)
1. **Borrador**: Creado de forma manual. Espera confirmación.
2. **Pendiente**: Registrado en firme. Si tiene cotización especial activa, levanta una incidencia y no avanza hasta que se resuelva el precio.
3. **En Diseño**: Tarea asignada a un Diseñador.
4. **En Revisión**: Muestra subida para visto bueno del cliente.
5. **Aprobado para Imprimir**: Archivo de salida transferido y enlazado a la cola de producción.
6. **En Producción**: Operadores procesando el material.
7. **Listo para Instalar / Entregar**: En espera de despacho o equipo de campo.
8. **Completado**: Finalizado (con pruebas fotográficas adjuntas si fue instalado).

## 5. Estructura y Gestión de Archivos (Core Anti-Redundancia)
Para evitar la saturación del servidor con archivos duplicados, el sistema divide el almacenamiento en "Master Data" y "Archivos Transaccionales".

**A. Banco de Activos Permanentes (Master Data):**
`[Disco_Servidor]:\TaskCore_Archivos\[ID_CLIENTE]_[Nombre_Cliente]\Activos_Permanentes\`
Aquí residen logos vectorizados, tipografías y manuales de marca. Se suben una sola vez por cliente.

**B. Archivos Transaccionales (Órdenes de Trabajo):**
Al crear una orden (que no sea borrador), el sistema genera la siguiente ruta automática:
`[Disco_Servidor]:\Produccion_Grafica\[AÑO]\[MES]\[ID_CLIENTE]_[JOB_ID]_[Nombre_Proyecto]\`
* Los archivos originales y recursos del cliente se colocan directamente **en la raíz (sueltos)** de esta carpeta, junto con un enlace directo o simbólico (`ACCESO_DIRECTO_Activos_Permanentes`) a los activos permanentes del cliente.
* `\Editable`: Carpeta donde el diseñador guarda los archivos fuente y editables de diseño (`.ai`, `.psd`, `.cdr`, etc.). Al ser aprobado el trabajo, los editores aquí guardados se archivan automáticamente como enlaces duros en los activos del cliente.
* `\Salida_Impresion`: Archivos de salida finales listos para impresión o corte (PDF, TIFF, etc.). La aprobación del trabajo enlaza estos archivos a los directorios automáticos (`Hot Folders`) de producción.
* `\Muestras`: Previsualizaciones digitales, renders de muestra y fotos/guías de instalación.

## 6. Módulo de Búsqueda y Trazabilidad
* Buscador global integrado en la cabecera. Permite localizar ítems por ID de Orden, Nombre de Proyecto, Nombre de Cliente o Referencia.
* Diseñado bajo un principio de "Zero-Leakage": no expone precios ni balances financieros a roles restringidos en sus respuestas JSON ni en la vista del frontend.

## 7. Infraestructura de Red y Despliegue Híbrido
El sistema se ejecuta en un esquema híbrido que maximiza el rendimiento y minimiza las latencias de la sincronización de archivos:

* **Servicios Contenedores (Docker / WSL2)**:
  * **`taskcore_web`**: Contenedor Flask que corre en el puerto `80:5000`. Expone la interfaz web y la lógica de negocio a la intranet.
  * **`taskcore_db`**: Contenedor PostgreSQL que corre en el puerto `5432` con volumen mapeado (`db_data/`) para almacenamiento persistente del motor relacional.
* **Servicios Locales (Windows Host)**:
  * **Guardián de Archivos (`auto_watcher.py`)**: Script demonio que corre en segundo plano en Windows, monitoreando el estado de los archivos y generando los enlaces simbólicos y duros en el sistema de almacenamiento.
* **Orquestación Automática (`iniciar_sistema_docker.bat`)**:
  * Ejecuta de forma secuencial la limpieza de procesos huérfanos.
  * Levanta el ecosistema Docker Compose.
  * Optimización de compilación: Uso de `.dockerignore` para excluir carpetas pesadas (`venv`) reduciendo el tiempo de transferencia del build context de minutos a milisegundos.

## 8. Reglas de Usabilidad y Experiencia de Usuario (Prioridad #1 del Frontend)
* **PWA (Progressive Web App)**: Service Worker y manifest.json instalables con iconos vectoriales responsivos.
* **Tema Claro / Oscuro**: Toggle integrado con almacenamiento de preferencia en `localStorage`.
* **Notificaciones No Invasivas**: Toasts reactivos mediante Alpine.js para confirmaciones, errores e incidencias resueltas.
* **Autocompletados**: Carga dinámica de tasas de cambio y autocompletado de clientes en el formulario de creación manual.
* **Inventario Dinámico**: Módulo ligero que permite reportar estados de materiales (ej. "Queda media bobina de Vinil Matte") con alertas directas para la administración. 

## 9. Desinstalación y Limpieza del Sistema (Preparación de Marca Blanca)
Para revertir completamente la instalación o limpiar el entorno para un despliegue de marca blanca, se incluye el archivo `desinstalar_sistema.bat`. Este script solicita permisos de Administrador y realiza lo siguiente:
* Cierra todos los procesos locales de Python, y detiene los contenedores Docker Compose (`docker compose down -v`).
* Limpia del registro de Windows las claves de protocolo personalizado `taskcore://` y las políticas de exclusión de auto-lanzamiento en los navegadores Chrome, Edge y Opera.
* Remueve la asignación del DNS local `taskcore` del archivo hosts de Windows.
* Ofrece opciones para borrar directorios locales de producción (`TaskCore_Archivos`), bases de datos SQLite temporales (`test.db` / `sistema_gestion_produccion_test.db`), el entorno virtual `venv`, y archivos de configuración (.env).