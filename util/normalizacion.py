"""
util/normalizacion.py
Funciones de normalización de texto y números para los parsers del SRI.
"""
import re


def extraer_xml_interno(texto):
    """
    Extrae el XML interno del CDATA de un comprobante electrónico SRI.
    Los XMLs del SRI envuelven el comprobante real en:
      <comprobante><![CDATA[<?xml ...><factura>...</factura>]]></comprobante>
    Si no hay CDATA, devuelve el texto tal cual.

    Raises:
        ValueError: Si el contenido parece HTML (ej. página de error del portal SRI).
    """
    stripped = texto.strip()
    if stripped.startswith('<!DOCTYPE') or stripped.lower().startswith('<html'):
        raise ValueError(
            "El archivo contiene HTML en lugar de XML. "
            "Posiblemente la sesión del portal SRI expiró durante la descarga. "
            "Vuelve a descargar el comprobante."
        )
    match = re.search(r'<!\[CDATA\[(.*?)\]\]>', texto, re.DOTALL)
    return match.group(1) if match else texto


def formatear_num_documento(numero):
    """
    Normaliza un número de comprobante al formato estándar 001-001-000005254.

    Transformaciones aplicadas:
      - Elimina prefijos textuales del sistema contable: "FAC ", "RET ", "NC ", etc.
      - Convierte 15 dígitos continuos: 001001000005254 → 001-001-000005254.
      - Si ya tiene el formato con guiones, lo devuelve limpio.
    """
    s = str(numero).strip()
    # Quitar prefijos que el sistema contable añade antes del número
    # Ej: "FAC 001-001-034380415" → "001-001-034380415"
    s = re.sub(r'^[A-Z]{1,5}[\.\s]+', '', s).strip()
    if re.match(r'^\d{15}$', s):
        return f"{s[:3]}-{s[3:6]}-{s[6:]}"
    return s


def safe_float(valor, default=0.0):
    """
    Convierte a float de forma tolerante a formatos con coma decimal,
    símbolo de moneda, espacios, o valores None/vacíos.

    Ejemplos:
        "1.234,56" → 1234.56
        "$12.50"   → 12.50
        "N/A"      → 0.0
        None       → 0.0

    Args:
        valor: Valor a convertir (str, int, float, None).
        default (float): Valor devuelto si la conversión falla.

    Returns:
        float
    """
    if valor is None:
        return default
    s = str(valor).strip()
    if not s:
        return default
    # Eliminar símbolo de moneda y espacios
    s = re.sub(r'[$\s]', '', s)
    # Normalizar separador decimal: si hay coma y punto, la coma es el decimal
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except (ValueError, OverflowError):
        return default
