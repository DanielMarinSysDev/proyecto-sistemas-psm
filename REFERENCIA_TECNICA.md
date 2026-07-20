# Referencia Técnica: Sistema TaskCore

Este documento sirve como "Hoja de Trucos" (Cheat Sheet) y guía de referencia estricta para desarrolladores o agentes de IA que vayan a modificar el código fuente en el futuro. 
**El objetivo de este archivo es evitar que se rompan funciones existentes por desconocimiento de las variables y parámetros del sistema.**

## 1. Valores Estrictos de Base de Datos (Enums)

El sistema utiliza `Enum` de SQLAlchemy. Es **CRÍTICO** usar el `.value` exacto en las plantillas Jinja2 (`{% if session.get('usuario_rol') == '...' %}`).

### Roles de Usuario (`RolEnum`)
Al registrar o verificar sesiones, el valor exacto en texto (`session['usuario_rol']`) es:
*   `'Administrador'`
*   `'Gerencia'`
*   `'Ventas / Recepción'`
*   `'Diseñador'`
*   `'Operador de Producción'`
*   `'Instaladores / Operaciones de Campo'`

**⚠️ Importante:** NUNCA usar 'ADMIN' o 'VENTAS' como string directo en Jinja, siempre usar el valor exacto (ej. `'Ventas / Recepción'`).

### Estados de Orden (`EstadoOrdenEnum`)
Los estados por los que viaja una `OrdenTrabajo` en el Kanban:
1.  `'Borrador'` (Color: Gris/Punteado - Para borradores de pre-cotizaciones manuales)
2.  `'Pendiente'` (Color: Gris/Azul oscuro)
3.  `'En Diseño'` (Color: Azul)
4.  `'En Revisión'` (Color: Naranja)
5.  `'Aprobado para Imprimir'` (Color: Verde)
6.  `'En Producción'` (Color: Morado)
7.  `'Listo para Instalar'` (Color: Cyan/Móvil)
8.  `'Completado'` (Desaparece del Kanban activo)

## 2. Variables de Sesión Activas (Flask Session)
Cuando un usuario hace Login, el diccionario `session` de Flask almacena:
*   `session['usuario_id']` (Integer)
*   `session['usuario_nombre']` (String)
*   `session['usuario_rol']` (String exacto del RolEnum.value)

## 3. Nuevos Campos y Configuración en Base de Datos
Al realizar modificaciones en los modelos de base de datos (`database_models.py`), recuerde importar el tipo `Boolean` desde SQLAlchemy.
*   **`Pedido.ocultar_precio_ventas`** (`Boolean`): Restringe la visualización del importe total del pedido y el desglose de abonos en el Kanban y Cuentas por Cobrar.
*   **`OrdenTrabajo.requiere_cotizacion`** (`Boolean`): Indica si el artículo requiere un cálculo manual de precio, bloqueando el avance en el Kanban.

## 4. Estructura de Endpoints Protegidos (RBAC)
Para proteger una ruta en Flask (`app.py` o Blueprints), se deben usar **dos decoradores** en este orden exacto:
```python
@login_required
@role_required(RolEnum.ADMIN, RolEnum.VENTAS)
def mi_ruta():
    pass
```

## 5. Rutas Físicas de Archivos y Anti-Redundancia
El motor `file_manager.py` genera la siguiente estructura física basada en la variable de entorno `BASE_DIR` (los borradores se omiten de este proceso hasta que se confirman):
### Master Data (Logos, manuales)
`%BASE_DIR%\CLIENTES_MASTER_DATA\[ID_Cliente]_[Nombre_Empresa]\Activos_Permanentes`
### Órdenes Transaccionales (Trabajos diarios)
`%BASE_DIR%\Produccion_Grafica\[AÑO]\[MES]\[ID_Cliente]_[JOB_ID]_[Proyecto]`
*   `Editable` (Editables de Illustrator, Photoshop, Corel. Al aprobar la orden, se enlazan de forma dura en `Activos_Permanentes`).
*   `Salida_Impresion` (Finales TIFF/PDF enlazados a Hot Folders).
*   `Muestras` (Previews y pruebas fotográficas de instalación).

## 6. Endpoints de la API (AJAX)
*   `POST /api/login` / `POST /api/logout`: Sesión.
*   `POST /api/ordenes`: Crea una orden de trabajo real o borrador (`es_borrador: true`). Si el rol no es Admin o Gerencia, se fuerza `ocultar_precio_ventas = False` en el backend.
*   `GET /api/borradores` / `POST /api/borradores/<id>/confirmar` / `POST /api/borradores/<id>/editar` / `DELETE /api/borradores/<id>`: Ciclo de vida de borradores. Al confirmar, si el rol no es Admin o Gerencia, se fuerza `ocultar_precio_ventas = False`.
*   `PUT /api/incidencias/<id>/resolver`: Resuelve incidentes (como cotizaciones especiales). Protegido estrictamente con `@role_required(RolEnum.ADMIN, RolEnum.GERENCIA)`. Acepta `{ monto_aprobado, ocultar_precio_ventas }` para cotizaciones especiales.
*   `GET /api/finanzas/deudores` y `/api/finanzas/deudores/<id>/pedidos`: Cuentas por cobrar con ofuscación de montos según el rol de la sesión.
*   `GET /api/buscar?q=...`: Búsqueda global (segura, no expone datos financieros).
*   `GET /usuarios`: Panel de administración de usuarios. Acceso para `Administrador` y `Gerencia`.
*   `POST /api/usuarios` / `PUT /api/usuarios/<id>` / `DELETE /api/usuarios/<id>`: Gestión de usuarios (Crear, Editar, Eliminar). Permitido para `Administrador` y `Gerencia`. Si el usuario activo es `Gerencia`, el backend y frontend bloquean y validan que solo se operen cuentas con roles inferiores a Gerencia (no se puede crear/editar/eliminar a Administradores u otros Gerentes).
*   `GET /api/clientes/<id>/expediente`: Endpoint de Master Data que retorna el expediente digital completo (saldo a favor, ruta master y array de órdenes enriquecido con `url_preview`, `url_descarga` y clasificación `tipo`).
*   `GET /api/ordenes/<id>/preview/<filename>`: Endpoint para la generación de thumbnails y previsualización segura de imágenes en línea.
*   `GET /api/ordenes/<id>/descargar-archivo/<filename>`: Endpoint seguro para servir la descarga directa de archivos adjuntos usando `send_from_directory`.
*   `POST /api/mantenimiento/respaldar` / `POST /api/mantenimiento/restaurar`: Mantenimiento y copias de seguridad de la base de datos PostgreSQL.
*   `POST /api/admin/system/update`: Actualización remota del sistema desde el repositorio de Git.

## 7. Apariencia, Temas y Estándar de Impresión A4
*   **Azul Corporativo:** `#0278D2`
*   **Tema Claro/Oscuro:** Gestionado en el cliente vía `toggleTheme()` en `base.html`. Guarda la preferencia de usuario en `localStorage.theme` y añade la clase `.dark` a la etiqueta `<html>`. Selectores específicos `.light` fuerzan el contraste tipográfico (`text-slate-100` y `text-slate-200` ajustados a slate oscuro) evitando invisibilidad en fondo claro.
*   **Estándar de Impresión PDF / A4 (`@media print`)**:
    *   Plantillas estandarizadas: `reportes.html` y `auditoria.html`.
    *   Uso obligatorio del **SVG oficial de 20 trazos** (`viewBox="0 0 1442.46 170.18"`) en el header de impresión para preservar la tipografía completa `TASKCORE` sin recortes.
    *   Estructura DOM estricta: Las etiquetas SVG de impresión deben cerrarse limpiamente (`</svg>`) sin caracteres extra y aisladas en el contenedor `.print-only` para prevenir que el footer invada el header.
*   **Interactividad:** Controlada con Alpine.js. Las variables globales reactivas se inicializan directamente en los nodos contenedores con `x-data`.

## 8. Despliegue, Puertos y Variables de Entorno
### Puertos Clave:
*   **`80` (Externo) / `5000` (Interno)**: Servidor web Flask (`taskcore_web` en Docker).
*   **`5432`**: Base de datos PostgreSQL (`taskcore_db` en Docker).

### Variables de Entorno (.env / OS):
*   `DATABASE_URL`: URL de conexión (Ej: `postgresql://taskcore_user:taskcore_pass_123@localhost:5432/sistema_taskcore`).
*   `BASE_DIR`: Directorio de archivos base (Ej: `E:\TaskCore_Archivos` o `%CD%\TaskCore_Archivos`).
*   `DB_DATA_DIR`: Directorio en el Host para los archivos de la base de datos (Ej: `E:\db_data` o `./db_data`).

### Orquestación de Construcción y Ejecución:
*   **Producción / Prueba Integral**: Ejecutar `iniciar_sistema_docker.bat`. Este script levanta Docker Compose y arranca los procesos locales.
*   **Desarrollo Local**: Si se requiere levantar el contenedor `taskcore_db` (para PostgreSQL) y ejecutar `iniciar_sistema.bat` para correr Flask nativamente en Windows (`http://localhost`).
*   **Optimización**: El archivo `.dockerignore` previene la transferencia de `venv/` y base de datos local al build de Docker, reduciendo el peso del contexto de construcción a <1MB y acelerando los arranques.

## 9. Protocolo Personalizado de Red (`taskcore://`)

Para abrir carpetas locales del servidor directamente desde los navegadores de las PCs clientes de la intranet, el sistema utiliza un protocolo URI personalizado de Windows:
*   **Construcción de la URL:** En el frontend, se hace una redirección a `taskcore://[BASE64_DE_LA_RUTA]?server=[HOST_NUEVO]`. Se codifica en Base64 para evitar que los navegadores mutilen las barras invertidas (`\`) y caracteres especiales de Windows (como acentos o la `ñ`).
*   **Compatibilidad con Contextos Inseguros (HTTP):** La API del portapapeles (`navigator.clipboard`) está bloqueada por el navegador en entornos HTTP remotos. Para evitar crasheos fatales de JavaScript, las llamadas a `navigator.clipboard.writeText` se resguardan bajo la condicional `if (navigator.clipboard && navigator.clipboard.writeText)`.
*   **Funcionamiento del Handler (PowerShell en Registro):**
*       Si se ejecuta en el **Servidor** (la IP de la URL coincide con alguna IP local de la máquina), se abre la ruta directa en el disco (ej. `E:\TaskCore_Archivos\...`), evadiendo el bloqueo de loopback de Windows (LSA Loopback Check).
*       Si se ejecuta en una **PC Cliente**, traduce la ruta local al recurso compartido por red (ej. `\\192.168.0.19\TaskCore_Archivos\...` o `\\100.80.218.32\TaskCore_Archivos\...`).
*       **Regla de Precedencia en PowerShell:** El comando del registro utiliza la sintaxis `$path = $path -replace 'patron', ('\\' + $resolved + '\$1')`. Los paréntesis son **estrictamente obligatorios** para que la concatenación de texto `+` no sea agrupada por la coma del operador `-replace`, lo que provocaría un error de ejecución en PowerShell.
*       **Logs de Depuración:** Cualquier error o paso de la ejecución del protocolo en Windows se escribe en el archivo local `C:\Users\Public\taskcore_debug.txt`.

## 10. Gestión de Tarifas, Laminación y Acabados de Banner

*   **Excepción de Laminado para Vinil Transparente**:
    *   Si el material es `Vinil Transparente`, la tarifa de laminación por m² se evalúa como `$0.00` en el backend, anulando cualquier valor de `laminado=True` para prevenir cargos redundantes de laminación en sí mismo.
    *   En la interfaz, los materiales `Microperforado` y `Vinil Transparente` desmarcan automáticamente la casilla de laminación.
*   **Acabados de Banner Dinámicos**:
    *   Los acabados y adicionales de `Banner` (ej: *Bastidor Madera*, *Bastidor Metal*, *Ojetes*, *Pendón Armado*) se almacenan en la base de datos con `tipo_trabajo = 'Banner'` y `es_adicional = True`.
    *   La recepción carga dinámicamente esta lista desde la API, eliminando la necesidad de selectores anidados o valores estáticos.
*   **Semaforización de Categorías**:
    *   En la vista de Gestión de Tarifas, la columna **Tipo** utiliza etiquetas badge de color distintivas para identificar visualmente si un registro representa un **Material Base** o un **Acabado/Adicional** (`es_adicional=True`).

## 11. Desinstalación y Limpieza del Sistema (Marca Blanca)

Para revertir los cambios de red, registro y firewall realizados en el sistema operativo durante la instalación/configuración de la PC cliente y servidor, se dispone del script `desinstalar_sistema.bat`:
*   **Procesos**: Detiene de forma forzada los servicios locales en ejecución (`python.exe`, y contenedores Docker Compose mediante `docker compose down -v`).
*   **Registro**: Borra la clave `HKEY_CLASSES_ROOT\taskcore` y las políticas de auto-lanzamiento de protocolos (`AutoLaunchProtocolsFromOrigins`) de Chrome, Edge y Opera en HKEY_LOCAL_MACHINE y HKEY_CURRENT_USER.
*   **Hosts**: Analiza y purga de forma segura el mapeo DNS `192.168.0.19    taskcore` o cualquier entrada que contenga la palabra clave `taskcore` del archivo `%windir%\System32\drivers\etc\hosts` mediante un comando automatizado de PowerShell.
*   **Limpieza de Archivos Opcional**: Ofrece menús interactivos para purgar de manera definitiva los archivos de almacenamiento de producción (`TaskCore_Archivos`), bases de datos SQLite locales (`test.db` y `sistema_gestion_produccion_test.db`), el entorno virtual de Python (`venv`), y archivos de configuración (.env).
