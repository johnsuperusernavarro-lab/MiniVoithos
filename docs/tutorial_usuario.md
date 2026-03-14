# Tutorial de Usuario — VOITHOS

## ¿Qué es VOITHOS?

VOITHOS es una herramienta de auditoría contable diseñada para contribuyentes
del **SRI de Ecuador**. Automatiza la tarea mensual de comparar tres fuentes
de información y detectar discrepancias antes de que se conviertan en problemas:

| Fuente | Descripción |
|--------|-------------|
| **XMLs del SRI** | Facturas y retenciones electrónicas descargadas del portal |
| **TXT del SRI** | Listado de comprobantes "Recibidos" exportado del portal |
| **Sistema contable** | ReporteComprasVentas.xlsx exportado del sistema interno |
| **Ventas Personalizado** | Excel auxiliar de ventas con retenciones recibidas |

El resultado es un **reporte Excel** con código de colores que muestra exactamente
qué facturas o retenciones tienen discrepancias.

---

## Preparar la carpeta de datos

VOITHOS detecta automáticamente los archivos si usas los nombres convencionales.

### Estructura recomendada de carpetas

```
enero_2026/                          ← carpeta raíz del mes (puedes arrastrarla)
│
├── enero compras 2026/              ← XMLs + PDFs de facturas de compra
│     ├── Factura(1).xml
│     ├── Factura(1).pdf
│     ├── Factura(2).xml
│     └── ...
│
├── Enero Retenciones 2026/          ← XMLs + PDFs de retenciones recibidas
│     ├── Retencion(1).xml
│     ├── Retencion(1).pdf
│     └── ...
│
├── SRI_TXT/                         ← TXT exportado del portal SRI
│     └── 1711516144001_Recibidos.txt
│
├── ReporteComprasVentas.xlsx        ← Exportado del sistema contable
│
└── Ventas_Personalizado.xlsx        ← Excel auxiliar de ventas (opcional)
```

### Cómo descargar los archivos del portal SRI

**XMLs de facturas y retenciones:**
1. Ingresa al portal SRI → Comprobantes Electrónicos → Recibidos
2. Filtra por período (ej: enero 2026)
3. Descarga todos los XMLs y PDFs en una carpeta

**TXT de comprobantes recibidos:**
1. Portal SRI → Comprobantes Electrónicos → Recibidos
2. Clic en "Exportar" → formato TXT
3. Guarda el archivo en la carpeta `SRI_TXT/`

**ReporteComprasVentas.xlsx:**
1. Exporta desde tu sistema contable el reporte de compras y ventas del período
2. Asegúrate de que tenga las secciones COMPRAS y VENTAS en la misma hoja

---

## Cómo ejecutar VOITHOS

### Opción A — Interfaz gráfica (recomendada para uso diario)

1. Abre `VOITHOS.exe` (o ejecuta `python main.py`)
2. **Arrastra** la carpeta del mes al área de drag & drop central
3. Verifica que los 5 campos se rellenaron automáticamente
4. Si algún campo quedó vacío, usa el botón `...` para buscarlo manualmente
5. Clic en **▶ EJECUTAR**
6. Espera entre 10 y 60 segundos (depende del número de XMLs)
7. Cuando el botón "Abrir Reporte" se ponga verde, haz clic en él

### Opción B — Línea de comandos

```bash
# Análisis completo (solicita la carpeta interactivamente)
python main.py analizar

# Análisis completo con carpeta especificada directamente
python main.py analizar --carpeta "C:/datos/enero_2026"

# Solo comparar compras
python main.py compras --carpeta "C:/datos/enero_2026"

# Solo comparar retenciones
python main.py retenciones --carpeta "C:/datos/enero_2026"

# Solo renombrar y organizar PDFs
python main.py renombrar_pdfs --carpeta "C:/datos/enero_2026"

# Abrir la interfaz gráfica
python main.py gui
```

---

## Entender el reporte Excel

El reporte generado (`AUDITORIA_YYYYMMDD_HHMMSS.xlsx`) tiene 7 hojas:

### Hoja RESUMEN

La primera hoja que debes revisar. Muestra métricas clave:

```
COMPRAS
  Facturas en XMLs descargados          223
  Facturas en Sistema                   193
  Facturas en TXT del SRI               220
  Coinciden en los 3 orígenes           185
  En SRI pero NO en Sistema              30    ← aparece en ROJO si > 0
  Solo en Sistema (sin SRI / sin XML)     0    ← aparece en ROJO si > 0

RETENCIONES
  Retenciones en XMLs                    78
  Ventas con retención en Sistema        75
  Coinciden                              73
  XML sin registro en Sistema             2    ← aparece en ROJO si > 0
  Sistema sin XML de respaldo             2    ← aparece en ROJO si > 0
```

### Hojas de detalle

| Hoja | Color | Qué significa |
|------|-------|---------------|
| COMPRAS - No en Sistema | **Rojo** | Facturas que el SRI tiene registradas pero el sistema contable NO |
| COMPRAS - Solo en Sistema | **Naranja** | Facturas en el sistema sin respaldo en el SRI (posibles errores de digitación) |
| COMPRAS - Coincidencias | **Verde** | Todo OK. Revisar la columna "Diferencia" — si es ≠ 0 hay discrepancia de monto |
| RET - No en Sistema | **Rojo** | Retenciones en XML que no están registradas en el sistema |
| RET - Sin XML | **Naranja** | Retenciones registradas en el sistema sin XML de respaldo |
| RET - Coincidencias | **Verde** | Todo OK. Revisar columnas "Dif. IVA" y "Dif. IR" |

### Qué hacer con cada tipo de alerta

**Compras en SRI pero NO en Sistema (rojo):**
- Puede ser normal: gastos personales (combustible, supermercado) que el
  contable eligió no registrar.
- Si son gastos del negocio, deben registrarse en el sistema.

**Compras Solo en Sistema (naranja):**
- Posible error de digitación en el número de comprobante.
- Verificar que la factura efectivamente existe en el portal SRI.

**Retenciones sin registro en Sistema (rojo):**
- El cliente emitió una retención pero el sistema no la tiene.
- Contactar al cliente para confirmar y registrar.

**Diferencias de monto (columna "Diferencia" ≠ 0):**
- El monto del XML no coincide con el del sistema.
- Revisar cuál es el correcto y corregir.

---

## Carpeta de salida — processed_data/

Al ejecutar VOITHOS se crea automáticamente una carpeta `processed_data/`
junto al ejecutable (o al script). Contiene:

```
processed_data/
├── AUDITORIA_20260126_143022.xlsx    ← reporte Excel
├── compras/                          ← PDFs de facturas renombrados
│     ├── 001-001-000005254.pdf       ← nombre = serie de la factura
│     └── ...
└── retenciones/                      ← PDFs de retenciones renombrados
      ├── 001-001-000000089.pdf
      └── ...
```

Los PDFs renombrados facilitan la búsqueda: en lugar de `Factura(47).pdf`
tendrás `001-001-000005254.pdf` con el número oficial del comprobante.

---

## Instalación para desarrolladores

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/voithos.git
cd voithos

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar
python main.py
```

### Compilar a .exe

```bash
pip install pyinstaller
pyinstaller VOITHOS.spec
# El ejecutable quedará en dist/VOITHOS/VOITHOS.exe
```

---

## Preguntas frecuentes

**¿Qué significa "30 compras en SRI pero NO en Sistema"?**
Es normal si el contribuyente tiene gastos personales (supermercado, farmacias,
combustible personal) que el SRI registra pero el contable no necesita ingresar
al sistema contable del negocio.

**¿Por qué hay más XMLs de retenciones que registros en sistema?**
Porque algunas retenciones llegaron después de cerrar el período contable,
o porque aún no han sido ingresadas. Son las que aparecen en "RET - No en Sistema".

**¿El programa modifica mis archivos originales?**
No. VOITHOS solo lee los archivos originales. Los PDFs que copia a
`processed_data/` son copias, no se eliminan los originales.

**¿Funciona con datos de varios meses a la vez?**
Sí, siempre que pongas todos los XMLs y el TXT en las carpetas correspondientes.
El TXT del SRI también puede ser una carpeta con varios archivos mensuales.

**¿Qué versiones de Python son compatibles?**
Python 3.10 o superior. Probado con Python 3.14.

---

*VOITHOS — Auditor Contable SRI | Documentación v2.0*
