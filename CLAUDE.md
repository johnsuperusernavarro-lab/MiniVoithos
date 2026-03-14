# VOITHOS — Auditor Contable SRI
## Archivo de contexto para Claude Code

---

## ¿Qué es este proyecto?

**VOITHOS** es una herramienta de auditoría contable para contribuyentes del **SRI de Ecuador**.
Su función es comparar tres fuentes de datos y detectar discrepancias antes del cierre mensual:

| Fuente | Formato |
|--------|---------|
| Facturas electrónicas descargadas del SRI | XMLs (v2.1.0, codDoc=01) |
| Retenciones recibidas del SRI | XMLs (v2.0 y v1.0) |
| Comprobantes recibidos del portal SRI | TXT tab-separated, latin-1 |
| Sistema contable interno | `ReporteComprasVentas.xlsx` |
| Ventas con retenciones (opcional) | `Ventas_Personalizado.xlsx` |

El resultado es un **reporte Excel de 7 hojas con código de colores** que identifica
exactamente qué facturas o retenciones tienen discrepancias.

---

## Estado actual: versión de escritorio (`Mini_voithos_V2/`)

Aplicación Python de escritorio con GUI CustomTkinter + TkinterDnD2.
El usuario arrastra carpetas locales, el programa procesa y genera archivos en disco.

### Estructura de módulos (todos implementados y funcionando)

```
Mini_voithos_V2/
├── main.py                          # CLI argparse (analizar/compras/retenciones/gui)
├── config.py                        # configuración centralizada
│
├── parsers/
│   ├── facturas_xml.py              # SRI factura v2.1.0 → dict
│   └── retenciones_xml.py           # SRI retención v2.0/v1.0 → dict
│
├── parsers/sri_txt.py               # TXT portal SRI → DataFrame
│
├── loaders/
│   ├── sistema_excel.py             # ReporteComprasVentas.xlsx → (df_compras, df_ventas)
│   └── ventas_personalizado.py      # Ventas_Personalizado.xlsx → DataFrame
│
├── comparadores/
│   ├── comparar_compras.py          # lógica 3 vías (XML ∩ TXT ∩ Sistema)
│   └── comparar_retenciones.py      # lógica 2 vías (XML ∩ Ventas_Pers)
│
├── reportes/
│   └── generar_excel.py             # reporte Excel 7 hojas con colores
│
├── util/
│   ├── normalizacion.py             # extraer_xml_interno(), formatear_num_documento(), safe_float()
│   ├── archivos.py                  # cargar_xmls_carpeta(), copiar_pdfs_renombrados(), detectar_estructura()
│   ├── validacion.py                # validar_carpeta_xmls(), validar_excel(), sanitizar_nombre_archivo()
│   └── logger.py                    # logger singleton → processed_data/logs/
│
└── gui/
    └── gui_app.py                   # GUI Catppuccin Mocha, sidebar, drag & drop
```

### Dependencias desktop

```
pandas>=2.0.0
openpyxl>=3.1.0
customtkinter>=5.2.0   ← NO disponible en el navegador
tkinterdnd2>=0.3.0     ← NO disponible en el navegador
```

### Convenciones de código establecidas

- Los parsers **nunca lanzan excepciones** — devuelven `{'_ERROR': str, '_ARCHIVO': str}`.
- `cargar_xmls_carpeta()` continúa procesando aunque algunos XMLs fallen (log de errores).
- Todo acceso a nodos XML verifica explícitamente `None` antes de usar `.findtext()`.
- `safe_float()` en todos los valores monetarios (tolera comas, $, None).
- Nombres de archivo sanitizados con `sanitizar_nombre_archivo()` antes de escribir.
- Thread safety en la GUI: todos los updates de UI van por `self.after(0, lambda: ...)`.

---

## Próxima versión: VOITHOS Web (en el navegador)

### La idea central

**El procesamiento ocurre completamente en el navegador del usuario.**
No hay servidor de procesamiento. No hay uploads. Los archivos nunca salen de la máquina.

```
Usuario abre la URL (GitHub Pages, Netlify, etc.)
           ↓
El navegador descarga la app estática (HTML + JS + Pyodide WASM)
           ↓
Usuario arrastra sus archivos al navegador (drag & drop nativo)
           ↓
Python corre DENTRO del navegador vía WebAssembly (Pyodide)
           ↓
Los módulos core (parsers, comparadores, reportes) corren sin cambios
           ↓
El reporte Excel se genera en memoria del navegador
           ↓
El navegador descarga el archivo localmente (no pasa por ningún servidor)
```

### Por qué esto resuelve todos los problemas del modelo servidor

| Problema (modelo servidor) | Solución (modelo navegador) |
|---------------------------|----------------------------|
| Subida de archivos peligrosos al servidor | No hay servidor — no hay superficie de ataque |
| ZIP bombs, XML bombs, XXE | El daño queda en el tab del usuario, no en infraestructura compartida |
| Aislamiento entre usuarios | Cada tab es un proceso aislado por el SO |
| Colas, workers, Redis | No necesarios — cada usuario es su propio worker |
| Limpieza de archivos temporales | El garbage collector del navegador lo hace |
| Costo de servidor | Hosting estático = gratis (GitHub Pages) |
| Escalabilidad | Infinita — cada usuario escala consigo mismo |
| Privacidad de datos fiscales | Los XMLs nunca salen de la computadora del usuario |
| Cuellos de botella | No existen — no hay recurso compartido |

---

## Stack tecnológico: VOITHOS Web

### Runtime de Python en el navegador

**Pyodide** — Python 3.12 compilado a WebAssembly.

```
https://pyodide.org
```

Pyodide corre en el navegador y provee:
- Intérprete Python completo vía WASM
- `pandas` disponible como paquete oficial de Pyodide
- `openpyxl` disponible como paquete oficial de Pyodide
- `xml.etree.ElementTree` disponible (stdlib Python, incluida en WASM)
- `defusedxml` instalable vía `micropip` dentro de Pyodide
- Interop bidireccional con JavaScript

### Módulos core — compatibilidad con Pyodide

| Módulo | Cambia en web | Qué cambia |
|--------|:---:|------------|
| `parsers/facturas_xml.py` | Mínimo | Recibe string/bytes en vez de path |
| `parsers/retenciones_xml.py` | Mínimo | Idem |
| `parsers/sri_txt.py` | Mínimo | Recibe bytes en vez de path |
| `loaders/sistema_excel.py` | Mínimo | Recibe bytes (BytesIO) en vez de path |
| `loaders/ventas_personalizado.py` | Mínimo | Idem |
| `comparadores/comparar_compras.py` | **Nada** | Lógica pura de DataFrames |
| `comparadores/comparar_retenciones.py` | **Nada** | Idem |
| `reportes/generar_excel.py` | Mínimo | Escribe a BytesIO en vez de path en disco |
| `util/normalizacion.py` | **Nada** | Funciones puras |
| `util/validacion.py` | Parcial | Sin os.path; validación de File objects del browser |
| `util/archivos.py` | Reemplazar | Sin filesystem — recibe File objects del browser |
| `util/logger.py` | Reemplazar | console.log del browser |
| `gui/gui_app.py` | **Reemplazar** | HTML/CSS/JS en vez de CustomTkinter |
| `config.py` | **Nada** | Constantes puras |

**Conclusión:** ≈80% del código Python se reutiliza sin cambios o con cambios mínimos.
Solo la GUI y las utilidades de filesystem se reescriben.

### Arquitectura de la versión web

```
voithos-web/
│
├── index.html                    ← app completa (single page)
├── style.css                     ← Catppuccin Mocha (misma paleta que el desktop)
│
├── js/
│   ├── app.js                    ← orquestador principal
│   ├── pyodide_loader.js         ← carga Pyodide + paquetes (con loading UI)
│   ├── file_handler.js           ← FileReader API, drag & drop, ZIP extraction
│   └── downloader.js             ← Blob → URL.createObjectURL → <a>.click()
│
├── py/                           ← módulos Python que corren en el navegador
│   ├── voithos_web.py            ← punto de entrada Python (llamado desde JS)
│   ├── parsers/                  ← MISMOS que desktop (cambio mínimo de API)
│   ├── loaders/                  ← MISMOS (reciben bytes/BytesIO)
│   ├── comparadores/             ← MISMOS (sin cambios)
│   ├── reportes/                 ← MISMOS (output a BytesIO)
│   ├── util/normalizacion.py     ← SIN CAMBIOS
│   └── util/validacion_web.py    ← versión web (sin os.path)
│
└── worker/
    └── analysis_worker.js        ← Web Worker para no bloquear la UI
```

### Flujo de ejecución en el navegador

```
1. CARGA (una vez)
   index.html se abre
   → pyodide_loader.js descarga Pyodide WASM (~10 MB, cacheable)
   → micropip instala pandas, openpyxl, defusedxml (primer uso)
   → módulos py/ se cargan en Pyodide
   → UI lista

2. SELECCIÓN DE ARCHIVOS
   Usuario arrastra carpeta o archivos individuales al drop zone
   → JavaScript lee los File objects (sin subir nada)
   → file_handler.js clasifica por tipo/nombre:
       *.xml → lista de facturas o retenciones (según nombre de carpeta padre)
       *.xlsx → sistema contable o ventas_personalizado
       *.txt  → TXT del SRI
       *.zip  → extraer en memoria (JSZip), clasificar contenido
   → UI muestra resumen: "47 XMLs de facturas, 23 XMLs retenciones, ..."

3. PROCESAMIENTO (en Web Worker — no bloquea la UI)
   JS pasa los File bytes a Python vía Pyodide
   → parsers reciben bytes, devuelven dicts
   → loaders reciben BytesIO, devuelven DataFrames
   → comparadores corren la lógica de conjuntos
   → reportes generan el Excel en un BytesIO
   → Python devuelve los bytes del Excel a JS

4. DESCARGA
   JS recibe los bytes del Excel
   → Blob + URL.createObjectURL
   → click programático en <a download="AUDITORIA_xxx.xlsx">
   → el archivo se descarga directamente (nunca sale al servidor)
```

### Interoperabilidad JS ↔ Python (Pyodide)

```javascript
// JS llama a Python
const resultado = await pyodide.runPythonAsync(`
    from voithos_web import analizar
    import json
    resultado = analizar(facturas_bytes, sistema_bytes, txt_bytes)
    json.dumps(resultado)
`);
```

```python
# Python recibe bytes desde JS
def parsear_factura_desde_bytes(contenido_bytes: bytes, nombre: str) -> dict:
    # misma lógica que parsear_factura_xml() pero sin open()
    raw = contenido_bytes.decode('utf-8', errors='replace')
    root = ET.fromstring(extraer_xml_interno(raw))
    # ... resto idéntico
```

```python
# Python genera Excel en memoria
import io
def generar_reporte_bytes(compras_r, retenciones_r) -> bytes:
    buf = io.BytesIO()
    generar_reporte(compras_r, retenciones_r, buf)   # misma función, output a BytesIO
    return buf.getvalue()
```

### Web Worker para procesamiento en background

```
Sin Web Worker: procesar 200 XMLs bloquea el tab → UI congelada
Con Web Worker: procesamiento en hilo separado → UI responsive

JavaScript (main thread)     JavaScript (Web Worker)
─────────────────────────    ──────────────────────────────
worker.postMessage(files) →  Pyodide.runPythonAsync(analisis)
                             ← worker.postMessage({progress: 45})
UI actualiza progress bar    ← worker.postMessage({done, bytes})
trigger descarga
```

### Manejo de seguridad en el modelo browser

La seguridad cambia de "proteger el servidor" a "proteger al usuario":

| Riesgo | Consecuencia en browser | Mitigación |
|--------|------------------------|------------|
| XML bomb / billion laughs | Congela el tab del usuario | `defusedxml` + timeout en Web Worker |
| ZIP bomb | Llena la RAM del tab | Verificar ratio antes de descomprimir con JSZip |
| Archivo malicioso | Daño local al usuario | No ejecutar nada, solo parsear |
| XSS en nombres de archivo | Inyección en la UI | Siempre escapar antes de insertar en el DOM |

El **sandbox del navegador** provee aislamiento adicional:
- El tab no puede acceder al filesystem del usuario (excepto lo que él sube explícitamente)
- El Worker no puede hacer requests a URLs externas (Content-Security-Policy)
- No hay acceso a otros tabs ni a otros usuarios

### Hosting

```
GitHub Pages (gratis, ya en GitHub):
  → push a main → deploy automático
  → URL pública sin costo
  → Sin límite de usuarios (estático puro)

Alternativas igualmente gratuitas:
  → Netlify, Vercel, Cloudflare Pages
```

---

## Decisiones de diseño que NO cambiar

1. **Los parsers devuelven `{'_ERROR': ...}` en caso de falla**, nunca lanzan excepciones.
   Esta convención es válida tanto en desktop como en web.

2. **`safe_float()` en todos los valores monetarios** — los XML del SRI ecuatoriano
   a veces tienen comas como separador decimal.

3. **La clave de cruce es `RUC_EMISOR + "|" + SERIE`** para compras,
   y `NO_FAC_SUSTENTO` para retenciones.

4. **El reporte tiene siempre 7 hojas**: RESUMEN, 3 de compras, 3 de retenciones.

5. **La paleta Catppuccin Mocha** se mantiene en la versión web:
   ```
   BASE=#1e1e2e  SURFACE0=#313244  TEXT=#cdd6f4
   BLUE=#89b4fa  GREEN=#a6e3a1    MAUVE=#cba6f7
   PEACH=#fab387 TEAL=#94e2d5     RED=#f38ba8
   ```

6. **`defusedxml`** en lugar de `xml.etree.ElementTree` directamente para todos los parsers.
   Disponible en Pyodide vía `micropip.install("defusedxml")`.

---

## Preguntas que Claude debe responder siempre así

**"¿Dónde se procesan los datos?"**
En el navegador del usuario. El servidor solo sirve archivos HTML/JS/CSS estáticos.
Los XML, Excel y TXT nunca salen de la computadora del usuario.

**"¿Cómo escala?"**
Cada usuario es su propio servidor. N usuarios = N instancias del navegador procesando en paralelo.
No hay recurso compartido que sea cuello de botella.

**"¿Es gratis?"**
Hosting estático en GitHub Pages = gratuito. Sin infraestructura de backend.

**"¿Qué tan diferente es del desktop?"**
La lógica core (~80% del código) es idéntica.
Solo cambian la GUI (HTML en vez de CustomTkinter) y el I/O de archivos
(FileReader API en vez de `open()`).

**"¿Funciona offline?"**
Sí, después de la primera carga. Pyodide y los paquetes se cachean en el browser.

---

## Comandos de desarrollo

```bash
# Desktop (actual)
cd Mini_voithos_V2
pip install -r requirements.txt
python main.py                          # GUI
python main.py analizar --carpeta RUTA  # CLI

# Compilar a .exe
pyinstaller VOITHOS.spec

# Tests manuales de módulos
python -c "from parsers.facturas_xml import parsear_factura_xml; print(parsear_factura_xml('ruta.xml'))"
```

```bash
# Web (próxima versión) — servidor de desarrollo local
python -m http.server 8080
# Abrir http://localhost:8080
# Pyodide requiere HTTPS en producción o localhost en desarrollo
```

---

## Historial de decisiones importantes

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-01 | Refactorizar monolito `voithos.py` (777 líneas) en módulos | Mantenibilidad y preparación para GitHub |
| 2026-01 | Rediseño GUI con Catppuccin Mocha (sidebar + 4 herramientas) | UX: comunicar acciones, no tipos de archivo |
| 2026-03 | Agregar `util/validacion.py` y `util/logger.py` | Robustez: el programa nunca debe crashear con input malo |
| 2026-03 | Usar `defusedxml` en parsers | Seguridad: XML bombs, XXE |
| 2026-03 | Evaluar y descartar arquitectura servidor para versión web | Cuellos de botella, costo, privacidad de datos fiscales |
| 2026-03 | Decidir arquitectura browser-first con Pyodide/WASM | Sin servidor = sin límites, gratis, privado, infinitamente escalable |
