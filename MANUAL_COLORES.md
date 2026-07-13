# Manual de Colores y Guía de Identidad Visual — TaskCore

Este documento detalla el sistema de diseño y la paleta de colores de **TaskCore**. Explica el comportamiento dinámico del sistema de temas (Claro y Oscuro), el mapeo de variables y cómo aplicar correctamente las clases semánticas para mantener consistencia en la interfaz.

---

## 1. Filosofía del Sistema de Temas
**TaskCore** utiliza un enfoque híbrido para la gestión de estilos visuales:
1. **Variables CSS Nativas (`styles.css`)**: Definen los valores exactos en hexadecimal para cada tema.
2. **Mapeo en Tailwind CSS (`base.html`)**: Transforma las clases utilitarias de Tailwind (como `bg-slate-900`, `text-slate-200`) para que consuman variables CSS de forma transparente.
3. **SVG Dinámicos**: Los logotipos e isotipos utilizan `fill="currentColor"` para cambiar de color de forma natural según el color de texto heredado del tema activo.

---

## 2. Paleta de Colores de Marca y Lienzo

### Tema Claro (Light Mode)
*Activado automáticamente al quitar la clase `.dark` del tag `<html>`.*

| Token Visual | Color Hex | Variable CSS | Propósito y Uso |
| :--- | :--- | :--- | :--- |
| **Color de Marca (Isotipo)** | `#0068A7` | `--brand-blue` | Azul Cobalto. Usado para destacar logos, botones primarios e inputs activos. |
| **Fondo Principal (Canvas)** | `#F6F8FA` | `--slate-50`, `--slate-900` | Gris ultra claro. Color de fondo del documento (`<body>`). |
| **Tarjetas/Paneles (Surface)**| `#FFFFFF` | `--slate-800`, `--slate-850`| Blanco puro. Contenedores de información y tarjetas de Kanban. |
| **Bordes/Líneas (Border)** | `#D0D7DE` | `--slate-300`, `--slate-700`| Gris suave. Separadores, bordes de inputs y divisores. |
| **Texto Principal (Title/Text)**| `#000000` | `--slate-200` | Negro sólido. Títulos, nombres de proyectos y texto principal. |
| **Texto Secundario (Muted)** | `#57606A` | `--slate-400`, `--slate-500`| Gris medio. Fechas, subtítulos y descripciones. |

---

### Tema Oscuro (Dark Mode) — *Tema Predeterminado*
*Activado mediante la clase `.dark` en el tag `<html>`.*

| Token Visual | Color Hex | Variable CSS | Propósito y Uso |
| :--- | :--- | :--- | :--- |
| **Color de Marca (Isotipo)** | `#00F0FF` | `--brand-blue` | Cian Eléctrico. Usado para destacar logos, botones primarios y acentos interactivos. |
| **Fondo Principal (Canvas)** | `#0B0F19` | `--slate-50`, `--slate-900` | Azul marino muy profundo. Color de fondo del documento (`<body>`). |
| **Tarjetas/Paneles (Surface)**| `#161B22` | `--slate-800`, `--slate-850`| Gris azulado oscuro. Contenedores de información y tarjetas de Kanban. |
| **Bordes/Líneas (Border)** | `#21262D` | `--slate-300`, `--slate-700`| Gris oscuro. Separadores, bordes de inputs y divisores. |
| **Texto Principal (Title/Text)**| `#FFFFFF` | `--slate-200` | Blanco puro. Títulos, nombres de proyectos y texto principal. |
| **Texto Secundario (Muted)** | `#8B949E` | `--slate-400`, `--slate-500`| Gris apagado. Fechas, subtítulos y descripciones. |

---

## 3. Estados de Tareas (Feedback Semántico)

Los estados del flujo de trabajo de producción cuentan con tonalidades diferenciadas por tema para garantizar la legibilidad (contraste mínimo WCAG) y estética premium:

| Estado Semántico | Color Claro (Hex) | Color Oscuro (Hex) | Variable CSS | Usado para... |
| :--- | :--- | :--- | :--- | :--- |
| **Completado (Éxito)** | `#2EA44F` (Verde medio) | `#3BA934` (Verde brillante) | `--sem-success` | Tareas terminadas, órdenes pagadas e incidencias resueltas. |
| **En Progreso (Pausado)**| `#D29922` (Ámbar/Ocre) | `#E7C300` (Amarillo vibrante) | `--sem-warning` | Trabajos en revisión de diseño, cotizaciones especiales activas. |
| **Atrasado (Alerta)** | `#CF222E` (Rojo sólido) | `#F92216` (Rojo neón) | `--sem-danger` | Órdenes arrastradas de días anteriores e incidencias activas. |

---

## 4. Guía de Uso del Código

### A. Uso de Clases Utilitarias Personalizadas (Recomendado)
Para simplificar la asignación de colores a bordes, textos y fondos sin preocuparse por la lógica de Light/Dark, use las clases utilitarias semánticas inyectadas en `styles.css`:

```html
<!-- Ejemplo: Tarjeta de incidencia en progreso -->
<div class="border-2 border-semantic-warning bg-semantic-warning/10 p-4 rounded-lg">
    <h4 class="text-semantic-warning font-bold">¡Incidencia de Material Detectada!</h4>
</div>

<!-- Ejemplo: Botón de Completar Orden -->
<button class="bg-semantic-success text-white px-4 py-2 rounded shadow">
    Completar Orden
</button>

<!-- Ejemplo: Etiqueta de Alerta por retraso -->
<span class="text-semantic-danger border border-semantic-danger px-2 py-0.5 rounded text-xs">
    Arrastrada
</span>
```

### B. Uso Directo en CSS / Hojas de Estilo
Si está programando un nuevo componente en CSS Vanilla, consuma las variables CSS directamente:

```css
.mi-boton-marca {
    background-color: var(--brand-blue);
    color: var(--slate-50); /* Adaptará automáticamente a blanco (oscuro) o negro (claro) */
    border: 1px solid var(--slate-300);
}

.mi-boton-marca:hover {
    background-color: var(--brand-blue-hover);
}
```

### C. Comportamiento en SVGs e Isotipo
Para que un archivo vectorial SVG se pinte del color del tema sin duplicar archivos físicos:
1. Asegúrese de que la etiqueta `<svg>` o sus elementos internos `<path>` usen el atributo `fill="currentColor"` o `stroke="currentColor"`.
2. Asigne la clase de color al contenedor del SVG.

```html
<!-- El Isotipo heredará automáticamente el cian eléctrico (oscuro) o azul cobalto (claro) -->
<div class="text-blue-500 w-8 h-8">
    <svg viewBox="0 0 478 549.31" fill="currentColor">
        <!-- Path data -->
    </svg>
</div>
```

---

## 5. Mapeo Interno de Tailwind
Para referencia de depuración, el archivo `base.html` configura el motor de Tailwind CSS para redirigir las clases predeterminadas hacia las variables dinámicas de la siguiente manera:

```javascript
tailwind.config = {
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                blue: {
                    500: 'var(--brand-blue)',       /* Color principal */
                    600: 'var(--brand-blue-hover)', /* Color Hover */
                },
                slate: {
                    50: 'var(--slate-50)',   /* Canvas */
                    100: 'var(--slate-100)',
                    200: 'var(--slate-200)', /* Texto principal */
                    300: 'var(--slate-300)', /* Borde */
                    400: 'var(--slate-400)', /* Texto atenuado */
                    500: 'var(--slate-500)',
                    600: 'var(--slate-600)',
                    700: 'var(--slate-700)',
                    800: 'var(--slate-800)', /* Superficie/Surface */
                    850: 'var(--slate-850)',
                    900: 'var(--slate-900)',
                    950: 'var(--slate-950)',
                }
            }
        }
    }
}
```
Esto garantiza que utilizar clases utilitarias de Tailwind como `bg-slate-800` renderizará un contenedor de fondo blanco puro `#FFFFFF` en modo claro, y un panel `#161B22` en modo oscuro de forma 100% nativa.
