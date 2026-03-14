"""
util/validacion.py
Validaciones de entrada para VOITHOS.

Todas las funciones públicas devuelven (ok: bool, mensaje: str).
Nunca lanzan excepciones — los errores se devuelven como strings para
que la GUI pueda mostrarlos directamente al usuario.
"""
import os
import re

# ── Límites defensivos ─────────────────────────────────────────────────────────
MAX_XML_FILES     = 2_000   # máximo de XMLs en una carpeta
MAX_XML_SIZE_MB   = 2       # los XML del SRI raramente superan 100 KB
MAX_EXCEL_SIZE_MB = 50
MAX_TXT_SIZE_MB   = 20

# Caracteres ilegales en nombres de archivo de Windows + caracteres de control
_ILEGALES_WIN = re.compile(r'[\\/*?:"<>|\x00-\x1f]')

# Columnas que aparecen en los reportes del sistema contable ecuatoriano
_CABECERAS_CONTABLES = {
    'NO_COMPROBANTE', 'NO_AUTORIZACION', 'FECHA_EMISION', 'FECHA',
    'PROVEEDOR', 'CLIENTE', 'RUC', 'RAZON_SOCIAL', 'BASE_IVA',
    'BASE_CERO', 'TOTAL', 'SUBTOTAL', 'IVA', 'VALOR', 'NO_RETENCION',
    'ESTABLECIMIENTO', 'PUNTO_EMISION', 'SECUENCIAL',
}


def validar_carpeta_xmls(ruta, label="carpeta"):
    """
    Verifica que la ruta sea una carpeta accesible con al menos un XML.

    Returns:
        (True, resumen) si OK
        (False, mensaje_de_error) si hay problema
    """
    if not ruta or not str(ruta).strip():
        return False, f"{label}: ruta vacía"
    ruta = str(ruta).strip()
    if not os.path.exists(ruta):
        return False, f"{label}: la ruta no existe:\n  {ruta}"
    if not os.path.isdir(ruta):
        return False, (
            f"{label}: se esperaba una CARPETA, no un archivo.\n"
            f"  '{os.path.basename(ruta)}' es un archivo — arrastra la carpeta que lo contiene."
        )
    if not os.access(ruta, os.R_OK):
        return False, f"{label}: sin permiso de lectura en '{os.path.basename(ruta)}'"
    try:
        xmls = [f for f in os.listdir(ruta) if f.lower().endswith('.xml')]
    except OSError as e:
        return False, f"{label}: error al leer la carpeta — {e}"
    if not xmls:
        return False, (
            f"{label}: no hay archivos .xml en '{os.path.basename(ruta)}'.\n"
            "  Verifica que hayas descargado los comprobantes del portal SRI."
        )
    if len(xmls) > MAX_XML_FILES:
        return False, (
            f"{label}: {len(xmls)} XMLs encontrados — el límite es {MAX_XML_FILES}.\n"
            "  Divide los archivos en subcarpetas mensuales."
        )
    return True, f"{len(xmls)} archivos XML"


def validar_zip_xmls(ruta, label="ZIP de comprobantes"):
    """
    Verifica que la ruta sea un archivo .zip accesible y no vacío.

    Returns:
        (True, resumen) si OK
        (False, mensaje_de_error) si hay problema
    """
    if not ruta or not str(ruta).strip():
        return False, f"{label}: ruta vacía"
    ruta = str(ruta).strip()
    if not os.path.exists(ruta):
        return False, f"{label}: el archivo no existe:\n  {ruta}"
    if os.path.isdir(ruta):
        return False, (
            f"{label}: se recibió una carpeta, se esperaba un archivo .zip.\n"
            "  Comprime la carpeta con los XML+PDF y arrastra el .zip."
        )
    if not ruta.lower().endswith('.zip'):
        return False, (
            f"{label}: extensión no reconocida — se esperaba un archivo .zip.\n"
            f"  Archivo recibido: '{os.path.basename(ruta)}'"
        )
    try:
        size_mb = os.path.getsize(ruta) / 1_048_576
    except OSError as e:
        return False, f"{label}: no se pudo leer el archivo — {e}"
    if size_mb > 200:
        return False, (
            f"{label}: el archivo tiene {size_mb:.0f} MB — el límite es 200 MB.\n"
            "  ¿Es el archivo correcto?"
        )
    if not os.access(ruta, os.R_OK):
        return False, f"{label}: sin permiso de lectura en '{os.path.basename(ruta)}'"
    import zipfile
    try:
        with zipfile.ZipFile(ruta, 'r') as zf:
            xmls = [m for m in zf.namelist() if m.lower().endswith('.xml')]
        if not xmls:
            return False, (
                f"{label}: el ZIP no contiene archivos .xml.\n"
                "  Verifica que hayas incluido los comprobantes descargados del SRI."
            )
        return True, f"{len(xmls)} archivos XML en el ZIP"
    except zipfile.BadZipFile:
        return False, f"{label}: el archivo ZIP está corrupto o no es válido."


def validar_excel(ruta, label="archivo Excel"):
    """
    Verifica que la ruta sea un .xlsx legible y no demasiado grande.

    Returns:
        (True, resumen) si OK
        (False, mensaje_de_error) si hay problema
    """
    if not ruta or not str(ruta).strip():
        return False, f"{label}: ruta vacía"
    ruta = str(ruta).strip()
    if not os.path.exists(ruta):
        return False, f"{label}: el archivo no existe:\n  {ruta}"
    if os.path.isdir(ruta):
        return False, f"{label}: se esperaba un archivo .xlsx, se recibió una carpeta"
    ext = os.path.splitext(ruta)[1].lower()
    if ext == '.xls':
        return False, (
            f"{label}: '{os.path.basename(ruta)}' es formato antiguo (.xls).\n"
            "  Ábrelo en Excel → Archivo → Guardar como → Libro de Excel (.xlsx)"
        )
    if ext not in ('.xlsx', '.xlsm'):
        return False, (
            f"{label}: extensión no reconocida '{ext or '(sin extensión)'}'.\n"
            "  Se esperaba un archivo .xlsx."
        )
    try:
        size_mb = os.path.getsize(ruta) / 1_048_576
    except OSError as e:
        return False, f"{label}: no se pudo leer el archivo — {e}"
    if size_mb > MAX_EXCEL_SIZE_MB:
        return False, (
            f"{label}: el archivo tiene {size_mb:.0f} MB — el límite es {MAX_EXCEL_SIZE_MB} MB.\n"
            "  ¿Es el archivo correcto?"
        )
    if not os.access(ruta, os.R_OK):
        return False, (
            f"{label}: sin permiso de lectura.\n"
            "  Si el archivo está abierto en Excel, ciérralo e intenta de nuevo."
        )
    return True, f"{os.path.basename(ruta)} ({size_mb:.1f} MB)"


def validar_txt_sri(ruta):
    """
    Verifica que la ruta sea un .txt o una carpeta con .txt del SRI.

    Returns:
        (True, resumen) si OK
        (False, mensaje_de_error) si hay problema
    """
    if not ruta or not str(ruta).strip():
        return False, "TXT SRI: ruta vacía"
    ruta = str(ruta).strip()
    if not os.path.exists(ruta):
        return False, f"TXT SRI: la ruta no existe:\n  {ruta}"
    if os.path.isdir(ruta):
        try:
            txts = [f for f in os.listdir(ruta) if f.lower().endswith('.txt')]
        except OSError as e:
            return False, f"TXT SRI: error al leer la carpeta — {e}"
        if not txts:
            return False, (
                "TXT SRI: la carpeta no contiene archivos .txt.\n"
                "  Exporta desde el portal SRI → Comprobantes Recibidos → Exportar."
            )
        return True, f"{len(txts)} archivo(s) TXT"
    ext = os.path.splitext(ruta)[1].lower()
    if ext not in ('.txt', '.tsv', '.csv'):
        return False, (
            f"TXT SRI: se esperaba un archivo .txt, se recibió '{ext or '(sin extensión)'}'"
        )
    try:
        size_mb = os.path.getsize(ruta) / 1_048_576
        if size_mb > MAX_TXT_SIZE_MB:
            return False, (
                f"TXT SRI: el archivo tiene {size_mb:.0f} MB — el límite es {MAX_TXT_SIZE_MB} MB"
            )
    except OSError:
        pass
    return True, os.path.basename(ruta)


def sanitizar_nombre_archivo(nombre):
    """
    Elimina caracteres inválidos en Windows y limita la longitud.
    Seguro para usar como nombre de archivo en cualquier SO.

    Args:
        nombre (str): Nombre propuesto (puede contener caracteres ilegales).

    Returns:
        str: Nombre limpio, máximo 200 caracteres.
    """
    limpio = _ILEGALES_WIN.sub('_', str(nombre))
    limpio = limpio.strip('. ')   # sin puntos ni espacios al inicio/fin
    return limpio[:200] if limpio else 'SIN_NOMBRE'


def es_ruta_segura(ruta_base, ruta_destino):
    """
    Verifica que ruta_destino no escape fuera de ruta_base (path traversal).

    Returns:
        bool: True si el destino está dentro de la base.
    """
    try:
        base = os.path.realpath(ruta_base)
        dest = os.path.realpath(ruta_destino)
        return dest == base or dest.startswith(base + os.sep)
    except Exception:
        return False


def fila_parece_cabecera(fila):
    """
    True si la fila tiene ≥ 2 celdas que coinciden con columnas contables conocidas.
    Más confiable que buscar cualquier celda que empiece con mayúsculas.

    Args:
        fila (tuple/list): Fila de valores de openpyxl.

    Returns:
        bool
    """
    celdas_norm = {
        str(c).strip().upper().replace(' ', '_')
        for c in fila if c is not None
    }
    return len(celdas_norm & _CABECERAS_CONTABLES) >= 2


def validar_rutas_analisis(tipo, rutas):
    """
    Valida las rutas necesarias para un tipo de análisis.
    Solo valida los campos requeridos; los opcionales se ignoran si están vacíos.

    Args:
        tipo (str): 'auditoria', 'compras', 'retenciones' o 'pdfs'.
        rutas (dict): Mapa {campo: ruta_string}.

    Returns:
        list[str]: Lista de mensajes de error. Lista vacía = todo OK.
    """
    errores = []

    requeridos_zip = {
        'auditoria':   ['facturas', 'retenciones'],
        'compras':     ['facturas'],
        'retenciones': ['retenciones'],
        'pdfs':        ['facturas'],
    }
    requeridos_excel = {
        'auditoria':   ['sistema'],
        'compras':     ['sistema'],
        'retenciones': ['ventas_pers'],
        'pdfs':        [],
    }
    requeridos_txt = {
        'auditoria': ['sri_txt'],
        'compras':   ['sri_txt'],
    }
    nombres_amigables = {
        'facturas':    'XMLs de Facturas de Compra',
        'retenciones': 'XMLs de Retenciones',
        'sistema':     'Sistema Contable (ReporteComprasVentas.xlsx)',
        'ventas_pers': 'Ventas Personalizado',
        'sri_txt':     'TXT del SRI',
    }

    for campo in requeridos_zip.get(tipo, []):
        val = rutas.get(campo, '').strip()
        if not val:
            errores.append(f"Falta: {nombres_amigables.get(campo, campo)}")
            continue
        # Acepta tanto .zip como carpeta (para compatibilidad con auto-detect)
        if os.path.isdir(val):
            ok, msg = validar_carpeta_xmls(val, nombres_amigables.get(campo, campo))
        else:
            ok, msg = validar_zip_xmls(val, nombres_amigables.get(campo, campo))
        if not ok:
            errores.append(msg)

    for campo in requeridos_excel.get(tipo, []):
        val = rutas.get(campo, '').strip()
        if not val:
            errores.append(f"Falta: {nombres_amigables.get(campo, campo)}")
            continue
        ok, msg = validar_excel(val, nombres_amigables.get(campo, campo))
        if not ok:
            errores.append(msg)

    for campo in requeridos_txt.get(tipo, []):
        val = rutas.get(campo, '').strip()
        if val:  # el TXT es requerido si se proporcionó; si está vacío es omitido
            ok, msg = validar_txt_sri(val)
            if not ok:
                errores.append(msg)

    return errores
