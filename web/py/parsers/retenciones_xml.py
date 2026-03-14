"""
parsers/retenciones_xml.py
Parser de comprobantes de retención XML del SRI.

Soporta dos versiones del esquema:
  - v2.0 (con <docSustento>): los campos del documento sustentado y los
    valores retenidos viven dentro del elemento <docSustento>.
  - v1.0 (sin <docSustento>): los campos están en <infoCompRetencion>
    y los valores en <impuestos>/<impuesto>.

Un XML v1.0 puede contener retenciones sobre múltiples documentos,
generando más de una fila por archivo.
"""
import os
from xml.etree import ElementTree as ET

from util.normalizacion import extraer_xml_interno, formatear_num_documento, safe_float

# Tamaño máximo que se acepta leer
_MAX_SIZE_BYTES = 2 * 1_048_576   # 2 MB


def parsear_retencion_xml(path):
    """
    Extrae los campos clave de un comprobante de retención XML del SRI.

    Defensas implementadas:
    - Rechaza archivos mayores a 2 MB antes de leerlos.
    - Detecta HTMLs (páginas de error del portal SRI).
    - Verifica explícitamente los nodos obligatorios <infoTributaria> e <infoCompRetencion>.
    - Convierte valores monetarios con safe_float.
    - Captura ParseError de XML con mensaje descriptivo.
    - Nunca lanza excepción: devuelve {'_ERROR': ...} en cualquier caso de falla.

    Campos devueltos:
      RUC_EMISOR_RET, RAZON_SOCIAL_RET, SERIE_RETENCION, CLAVE_ACCESO_RET,
      FECHA_RETENCION, PERIODO, NO_FAC_SUSTENTO, NO_AUT_SUSTENTO,
      IMPORTE_FAC, RET_IVA_XML, RET_IR_XML.

    Returns:
        dict: Datos de la retención, o {'_ERROR': str, '_ARCHIVO': str} si falla.
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
                          '¿es una retención v2.0 o v1.0?',
                '_ARCHIVO': nombre,
            }

        info_ret = root.find('infoCompRetencion')
        if info_ret is None:
            return {
                '_ERROR': 'Falta el nodo <infoCompRetencion> — '
                          '¿es un comprobante de retención del SRI?',
                '_ARCHIVO': nombre,
            }

        # ── Campos del emisor de la retención ─────────────────────────────────
        ruc    = info_trib.findtext('ruc',         '').strip()
        razon  = info_trib.findtext('razonSocial', '').strip()
        estab  = info_trib.findtext('estab',       '')
        pto    = info_trib.findtext('ptoEmi',      '')
        sec    = info_trib.findtext('secuencial',  '')
        clave  = info_trib.findtext('claveAcceso', '').strip()
        fecha  = info_ret.findtext('fechaEmision',  '')
        periodo = info_ret.findtext('periodoFiscal', '')

        # ── Valores de retención según versión del esquema ────────────────────
        doc = root.find('.//docSustento')
        if doc is not None:
            # Formato v2.0: toda la info dentro de <docSustento>
            no_fac  = doc.findtext('numDocSustento',     '').strip()
            no_aut  = doc.findtext('numAutDocSustento',  '').strip()
            importe = safe_float(doc.findtext('importeTotal'))
            ret_iva = ret_ir = 0.0
            for r in doc.iter('retencion'):
                cod = r.findtext('codigo', '')
                val = safe_float(r.findtext('valorRetenido'))
                if cod == '1':
                    ret_ir  += val
                elif cod in ('2', '3'):
                    ret_iva += val
        else:
            # Formato v1.0: datos en infoCompRetencion, retenciones en <impuestos>
            no_fac  = info_ret.findtext('numDocSustento',   '').strip()
            no_aut  = info_ret.findtext('numAutDocSustento', '').strip()
            importe = 0.0
            ret_iva = ret_ir = 0.0
            for imp in root.iter('impuesto'):
                cod = imp.findtext('codigo', '')
                val = safe_float(imp.findtext('valorRetenido'))
                if cod == '1':
                    ret_ir  += val
                elif cod in ('2', '3'):
                    ret_iva += val

        return {
            'RUC_EMISOR_RET':   ruc,
            'RAZON_SOCIAL_RET': razon,
            'SERIE_RETENCION':  f"{estab}-{pto}-{sec}",
            'CLAVE_ACCESO_RET': clave,
            'FECHA_RETENCION':  fecha,
            'PERIODO':          periodo,
            'NO_FAC_SUSTENTO':  formatear_num_documento(no_fac),
            'NO_AUT_SUSTENTO':  no_aut,
            'IMPORTE_FAC':      importe,
            'RET_IVA_XML':      ret_iva,
            'RET_IR_XML':       ret_ir,
            '_ARCHIVO':         nombre,
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
