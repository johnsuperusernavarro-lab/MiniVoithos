# VOITHOS — Auditor Contable SRI

Herramienta de auditoría contable para contribuyentes del **SRI de Ecuador**.
Compara facturas electrónicas, retenciones y registros del sistema contable para detectar discrepancias antes del cierre mensual.

---

## ¿Qué hace?

Cada mes el auxiliar contable recibe comprobantes electrónicos del SRI y debe verificar que coincidan con el sistema contable interno. VOITHOS automatiza ese proceso cruzando tres fuentes de datos:

| Fuente | Archivo |
|--------|---------|
| XMLs de facturas descargados | Carpeta con archivos `.xml` + `.pdf` |
| XMLs de retenciones recibidas | Carpeta con archivos `.xml` + `.pdf` |
| TXT del portal SRI | `*_Recibidos.txt` (tab-separated, latin-1) |
| Sistema contable | `ReporteComprasVentas.xlsx` |
| Ventas con retenciones | `Ventas_Personalizado.xlsx` (opcional) |

El resultado es un **reporte Excel con código de colores** que señala exactamente qué facturas o retenciones tienen discrepancias.

---

## Instalación rápida

```bash
git clone https://github.com/tu-usuario/voithos.git
cd voithos
pip install -r requirements.txt
python main.py
```

---

## Uso

### Interfaz gráfica (recomendada)

```bash
python main.py
```

Arrastra la carpeta del mes y haz clic en **EJECUTAR**.

### Línea de comandos

```bash
# Análisis completo
python main.py analizar --carpeta "C:/datos/enero_2026"

# Solo compras
python main.py compras --carpeta "C:/datos/enero_2026"

# Solo retenciones
python main.py retenciones --carpeta "C:/datos/enero_2026"

# Solo organizar PDFs
python main.py renombrar_pdfs --carpeta "C:/datos/enero_2026"
```

---

## Estructura del proyecto

```
Mini_voithos_V2/
│
├── main.py                    # Punto de entrada (GUI y CLI)
├── config.py                  # Configuración centralizada
├── requirements.txt
├── VOITHOS.spec               # Config de PyInstaller
│
├── parsers/                   # Lectores de archivos del SRI
│   ├── facturas_xml.py        # XMLs de facturas electrónicas
│   ├── retenciones_xml.py     # XMLs de retenciones (v1.0 y v2.0)
│   └── sri_txt.py             # TXT de comprobantes recibidos
│
├── loaders/                   # Cargadores del sistema contable
│   ├── sistema_excel.py       # ReporteComprasVentas.xlsx
│   └── ventas_personalizado.py
│
├── comparadores/              # Lógica de cruce de datos
│   ├── comparar_compras.py    # Comparación 3 vías (XML + TXT + Sistema)
│   └── comparar_retenciones.py# Comparación 2 vías (XML + Ventas_Personalizado)
│
├── reportes/
│   └── generar_excel.py       # Generador del reporte con 7 hojas
│
├── util/
│   ├── normalizacion.py       # Normalización de series y CDATA
│   └── archivos.py            # Carga masiva de XMLs, renombrado de PDFs,
│                              #   auto-detección de estructura
│
├── gui/
│   └── gui_app.py             # Interfaz gráfica drag & drop
│
└── docs/
    └── tutorial_usuario.md    # Guía paso a paso para el contable
```

---

## Reporte generado

El archivo `AUDITORIA_YYYYMMDD_HHMMSS.xlsx` tiene 7 hojas:

| Hoja | Color | Contenido |
|------|-------|-----------|
| RESUMEN | — | Métricas globales de compras y retenciones |
| COMPRAS - No en Sistema | Rojo | En SRI pero sin registro contable |
| COMPRAS - Solo en Sistema | Naranja | En sistema sin respaldo en SRI |
| COMPRAS - Coincidencias | Verde | Coincidentes (con columna "Diferencia") |
| RET - No en Sistema | Rojo | XML de retención sin registro |
| RET - Sin XML | Naranja | Retención en sistema sin XML |
| RET - Coincidencias | Verde | Coincidentes (con "Dif. IVA" y "Dif. IR") |

---

## Compilar a .exe

```bash
pip install pyinstaller
pyinstaller VOITHOS.spec
# Resultado: dist/VOITHOS/VOITHOS.exe  (standalone, no requiere Python)
```

---

## Dependencias

| Paquete | Uso |
|---------|-----|
| `pandas` | Manipulación de DataFrames y merges |
| `openpyxl` | Lectura del Excel del sistema y escritura del reporte |
| `customtkinter` | Widgets modernos para la GUI (tema oscuro) |
| `tkinterdnd2` | Soporte drag & drop nativo en Windows |

Módulos de la stdlib usados: `xml.etree.ElementTree`, `os`, `shutil`, `re`, `threading`, `queue`.

---

## Contexto

Diseñado para el flujo mensual de auditoría de contribuyentes del SRI de Ecuador.
El usuario final es un auxiliar contable, no un programador.
Compatible con los formatos XML v2.1.0 (facturas) y v2.0/v1.0 (retenciones).

---

## Licencia

MIT — Libre para uso y modificación.
