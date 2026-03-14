"""
config.py
Configuración centralizada de VOITHOS.
Modifica este archivo para ajustar el comportamiento del sistema.
"""

# ── Versión ───────────────────────────────────────────────────────────────────
VERSION = "2.0.0"
NOMBRE  = "VOITHOS — Auditor Contable SRI"

# ── Carpeta de salida ─────────────────────────────────────────────────────────
# Nombre de la subcarpeta donde se guardan los reportes y PDFs renombrados.
# Se crea dentro del directorio del ejecutable (o del script) al correr.
CARPETA_SALIDA = "processed_data"

# ── Carpetas internas de PDFs renombrados ─────────────────────────────────────
SUBCARPETA_COMPRAS     = "compras"
SUBCARPETA_RETENCIONES = "retenciones"

# ── Colores del reporte Excel (valores hex sin #) ─────────────────────────────
COLOR_TITULO    = "1F3864"   # azul oscuro — título de portada
COLOR_SECCION   = "2E75B6"   # azul — encabezados de sección
COLOR_ROJO      = "C00000"   # rojo — problemas críticos
COLOR_NARANJA   = "C55A11"   # naranja — advertencias
COLOR_VERDE     = "375623"   # verde — coincidencias correctas

# ── Configuración de lectura de archivos ──────────────────────────────────────
# Encoding del TXT del SRI (el portal exporta en latin-1)
ENCODING_TXT_SRI = "latin-1"

# Encoding de los XMLs del SRI
ENCODING_XML = "utf-8"

# ── Carpetas que se omiten en la auto-detección ───────────────────────────────
CARPETAS_OMITIR = {"processed_data", "__pycache__", ".git", "dist", "build"}
