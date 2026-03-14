"""
parsers/facturas_xml.py
Parser de facturas electrónicas XML del SRI (formato v2.1.0, codDoc=01).

Estructura del XML del SRI:
  <autorizacion>
    <comprobante><![CDATA[
      <?xml version="1.0"...>
      <factura>
        <infoTributaria>...</infoTributaria>
        <infoFactura>...</infoFactura>
        <detalles>...</detalles>
      </factura>
    ]]></comprobante>
  </autorizacion>
"""
import os
from xml.etree import ElementTree as ET

from util.normalizacion import extraer_xml_interno, safe_float

# Tamaño máximo que se acepta leer (los XML del SRI raramente superan 100 KB)
_MAX_SIZE_BYTES = 2 * 1_048_576   # 2 MB


def parsear_factura_xml(path):
    """
    Extrae los campos clave de una factura electrónica XML del SRI.

    Defensas implementadas:
    - Rechaza archivos mayores a 2 MB antes de leerlos.
    - Detecta HTMLs (páginas de error del portal SRI).
    - Verifica explícitamente los nodos obligatorios <infoTributaria> e <infoFactura>.
    - Convierte valores monetarios con safe_float (tolera comas, símbolos de moneda).
    - Captura ParseError de XML con mensaje descriptivo.
    - Nunca lanza excepción: devuelve {'_ERROR': ...} en cualquier caso de falla.

    Campos devueltos:
      RUC_EMISOR, RAZON_SOCIAL, SERIE (001-001-XXXXXXXXX),
      CLAVE_ACCESO, FECHA, BASE_15, BASE_5, BASE_0, SUBTOTAL, TOTAL.

    Returns:
        dict: Datos de la factura, o {'_ERROR': str, '_ARCHIVO': str} si falla.
    """
    nombre = os.path.basename(path)

    # ── Rechazo rápido por tamaño ─────────────────────────────────────────────
    try:
        if os.path.getsize(path) > _MAX_SIZE_BYTES:
            return {
                '_ERROR': f'Archivo demasiado grande (> {_MAX_SIZE_BYTES // 1_048_576} MB) — '
                          '¿es un XML del SRI?',
                '_ARCHIVO': nombre,
            }
    except OSError as e:
        return {'_ERROR': f'No se pudo acceder al archivo: {e}', '_ARCHIVO': nombre}

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            raw = f.read()

        # extraer_xml_interno lanza ValueError si detecta HTML
        contenido = extraer_xml_interno(raw)
        root = ET.fromstring(contenido)

        # ── Nodos obligatorios ────────────────────────────────────────────────
        info_trib = root.find('infoTributaria')
        if info_trib is None:
            return {
                '_ERROR': 'Falta el nodo <infoTributaria> — '
                          '¿es una factura v2.1.0? (codDoc=01)',
                '_ARCHIVO': nombre,
            }

        info_fac = root.find('infoFactura')
        if info_fac is None:
            return {
                '_ERROR': 'Falta el nodo <infoFactura> — '
                          '¿es una factura v2.1.0? (codDoc=01)',
                '_ARCHIVO': nombre,
            }

        # ── Extracción de campos ──────────────────────────────────────────────
        ruc   = info_trib.findtext('ruc',         '').strip()
        razon = info_trib.findtext('razonSocial', '').strip()
        estab = info_trib.findtext('estab',       '')
        pto   = info_trib.findtext('ptoEmi',      '')
        sec   = info_trib.findtext('secuencial',  '')
        clave = info_trib.findtext('claveAcceso', '').strip()
        fecha = info_fac.findtext('fechaEmision',  '')

        subtotal = safe_float(info_fac.findtext('totalSinImpuestos'))
        total    = safe_float(info_fac.findtext('importeTotal'))

        # Bases imponibles por tipo de IVA
        # cod '2' = IVA 15%, cod '5' = IVA 5%, cod '0' = IVA 0%
        base_15 = base_5 = base_0 = 0.0
        for imp in root.iter('totalImpuesto'):
            cod  = imp.findtext('codigoPorcentaje', '')
            base = safe_float(imp.findtext('baseImponible'))
            if cod == '2':
                base_15 = base
            elif cod == '5':
                base_5 = base
            elif cod == '0':
                base_0 = base

        return {
            'RUC_EMISOR':   ruc,
            'RAZON_SOCIAL': razon,
            'SERIE':        f"{estab}-{pto}-{sec}",
            'CLAVE_ACCESO': clave,
            'FECHA':        fecha,
            'BASE_15':      base_15,
            'BASE_5':       base_5,
            'BASE_0':       base_0,
            'SUBTOTAL':     subtotal,
            'TOTAL':        total,
            '_ARCHIVO':     nombre,
        }

    except ET.ParseError as e:
        return {
            '_ERROR': f'XML malformado: {e}. '
                      '¿El archivo se descargó correctamente del portal SRI?',
            '_ARCHIVO': nombre,
        }
    except ValueError as e:
        # Incluye el error de HTML detectado en extraer_xml_interno
        return {'_ERROR': str(e), '_ARCHIVO': nombre}
    except Exception as e:
        return {'_ERROR': str(e), '_ARCHIVO': nombre}
