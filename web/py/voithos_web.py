"""
voithos_web.py — Punto de entrada para la versión web (Pyodide).

El JavaScript escribe los archivos del usuario en el filesystem
virtual de Pyodide antes de llamar a las funciones de análisis.

Rutas esperadas en /tmp/voithos/:
  facturas/         carpeta con .xml  (o facturas.zip)
  retenciones/      carpeta con .xml  (o retenciones.zip)
  sistema.xlsx      ReporteComprasVentas
  comprobantes.txt  TXT del portal SRI  (opcional)
  ventas.xlsx       Ventas_Personalizado (opcional)

Funciones exportadas:
  analizar()           — Auditoría completa (compras + retenciones)
  analizar_compras()   — Solo facturas de compra
  analizar_retenciones()— Solo retenciones
  organizar_pdfs()     — Renombrar PDFs según serie del XML
  limpiar_tmp()        — Limpia /tmp/voithos/
"""
import base64
import io
import os
import shutil
import sys

import pandas as pd

sys.path.insert(0, '/home/pyodide')

from parsers.facturas_xml import parsear_factura_xml
from parsers.retenciones_xml import parsear_retencion_xml
from parsers.sri_txt import cargar_txt_sri
from loaders.sistema_excel import cargar_sistema
from loaders.ventas_personalizado import cargar_ventas_personalizado
from comparadores.comparar_compras import comparar_compras
from comparadores.comparar_retenciones import comparar_retenciones
from reportes.generar_excel import generar_reporte
from util.archivos import cargar_xmls_carpeta, extraer_zip_a_temp, pdfs_renombrados_a_zip

_TMP = '/tmp/voithos'

# ── Helpers internos ──────────────────────────────────────────────────────────

def _resolver_xmls(tipo: str):
    """
    Resuelve la carpeta de XMLs para 'facturas' o 'retenciones'.
    Prefiere carpeta sobre ZIP. Devuelve (carpeta, hay_que_limpiar).
    """
    ruta_dir = os.path.join(_TMP, tipo)
    ruta_zip = os.path.join(_TMP, f'{tipo}.zip')
    if os.path.isdir(ruta_dir):
        return ruta_dir, False
    if os.path.isfile(ruta_zip):
        return extraer_zip_a_temp(ruta_zip), True
    return None, False


def _cargar_facturas(advertencias):
    carpeta, limpiar = _resolver_xmls('facturas')
    if not carpeta:
        advertencias.append('No se encontraron XMLs de facturas.')
        return pd.DataFrame()
    df = cargar_xmls_carpeta(carpeta, parsear_factura_xml)
    if limpiar:
        shutil.rmtree(carpeta, ignore_errors=True)
    return df


def _cargar_retenciones(advertencias):
    carpeta, limpiar = _resolver_xmls('retenciones')
    if not carpeta:
        advertencias.append('No se encontraron XMLs de retenciones.')
        return pd.DataFrame()
    df = cargar_xmls_carpeta(carpeta, parsear_retencion_xml)
    if limpiar:
        shutil.rmtree(carpeta, ignore_errors=True)
    return df


def _cargar_sistema(advertencias):
    try:
        df_comp, _ = cargar_sistema(os.path.join(_TMP, 'sistema.xlsx'))
        return df_comp
    except ValueError as e:
        raise ValueError(str(e))


def _cargar_txt(advertencias):
    try:
        return cargar_txt_sri(os.path.join(_TMP, 'comprobantes.txt'))
    except Exception as e:
        advertencias.append(f'TXT SRI: {e}')
        return pd.DataFrame()


def _cargar_ventas(advertencias):
    try:
        return cargar_ventas_personalizado(os.path.join(_TMP, 'ventas.xlsx'))
    except ValueError as e:
        advertencias.append(str(e))
        return pd.DataFrame()


def _generar_excel(compras_r, ret_r):
    buf = io.BytesIO()
    generar_reporte(compras_r, ret_r, buf)
    return base64.b64encode(buf.getvalue()).decode()


# ── API pública ───────────────────────────────────────────────────────────────

def analizar(hay_facturas=False, hay_retenciones=False,
             hay_sistema=False, hay_txt=False, hay_vp=False):
    """
    Auditoría completa: compras + retenciones + reporte 7 hojas.

    Returns dict: excel_b64, stats_compras, stats_ret, advertencias.
    """
    adv = []

    df_fac  = _cargar_facturas(adv)    if hay_facturas    else pd.DataFrame()
    df_ret  = _cargar_retenciones(adv) if hay_retenciones else pd.DataFrame()
    df_comp = _cargar_sistema(adv)     if hay_sistema     else pd.DataFrame()
    df_txt  = _cargar_txt(adv)         if hay_txt         else pd.DataFrame()
    df_vp   = _cargar_ventas(adv)      if hay_vp          else pd.DataFrame()

    compras_r = comparar_compras(df_fac, df_txt, df_comp)
    ret_r     = comparar_retenciones(df_ret, df_vp)

    return {
        'excel_b64':     _generar_excel(compras_r, ret_r),
        'stats_compras': compras_r.get('stats', {}),
        'stats_ret':     ret_r.get('stats', {}),
        'advertencias':  adv,
    }


def analizar_compras(hay_facturas=False, hay_sistema=False, hay_txt=False):
    """
    Solo compras: compara XMLs de facturas contra TXT del SRI y sistema contable.

    Returns dict: excel_b64, stats_compras, advertencias.
    """
    adv = []

    df_fac  = _cargar_facturas(adv) if hay_facturas else pd.DataFrame()
    df_comp = _cargar_sistema(adv)  if hay_sistema  else pd.DataFrame()
    df_txt  = _cargar_txt(adv)      if hay_txt      else pd.DataFrame()

    compras_r = comparar_compras(df_fac, df_txt, df_comp)
    ret_r_vacio = {'coincidencias': pd.DataFrame(), 'sin_sistema': pd.DataFrame(),
                   'sin_xml': pd.DataFrame(), 'stats': {}}

    return {
        'excel_b64':     _generar_excel(compras_r, ret_r_vacio),
        'stats_compras': compras_r.get('stats', {}),
        'advertencias':  adv,
    }


def analizar_retenciones(hay_retenciones=False, hay_vp=False):
    """
    Solo retenciones: compara XMLs de retención contra Ventas_Personalizado.

    Returns dict: excel_b64, stats_ret, advertencias.
    """
    adv = []

    df_ret = _cargar_retenciones(adv) if hay_retenciones else pd.DataFrame()
    df_vp  = _cargar_ventas(adv)      if hay_vp          else pd.DataFrame()

    compras_r_vacio = {'coincidencias': pd.DataFrame(), 'no_en_sistema': pd.DataFrame(),
                       'solo_en_sistema': pd.DataFrame(), 'stats': {}}
    ret_r = comparar_retenciones(df_ret, df_vp)

    return {
        'excel_b64':  _generar_excel(compras_r_vacio, ret_r),
        'stats_ret':  ret_r.get('stats', {}),
        'advertencias': adv,
    }


def organizar_pdfs(hay_facturas=False, hay_retenciones=False):
    """
    Renombra los PDFs usando la serie extraída de los XMLs correspondientes
    y devuelve ZIPs en base64 listos para descargar.

    Returns dict:
      facturas_zip_b64    — ZIP de PDFs de facturas renombrados (o None)
      retenciones_zip_b64 — ZIP de PDFs de retenciones renombrados (o None)
      stats               — {facturas: {copiados, sin_pdf, errores}, retenciones: {...}}
      advertencias        — list[str]
    """
    adv   = []
    stats = {}
    fac_b64 = ret_b64 = None

    if hay_facturas:
        carpeta, limpiar = _resolver_xmls('facturas')
        if carpeta:
            zip_bytes, copiados, sin_pdf, errores = pdfs_renombrados_a_zip(
                carpeta, 'factura', parsear_factura_xml)
            if limpiar:
                shutil.rmtree(carpeta, ignore_errors=True)
            stats['facturas'] = {'copiados': copiados, 'sin_pdf': sin_pdf, 'errores': errores}
            if zip_bytes:
                fac_b64 = base64.b64encode(zip_bytes).decode()
            else:
                adv.append('No se encontraron PDFs de facturas para renombrar.')
        else:
            adv.append('No se encontraron XMLs de facturas.')

    if hay_retenciones:
        carpeta, limpiar = _resolver_xmls('retenciones')
        if carpeta:
            zip_bytes, copiados, sin_pdf, errores = pdfs_renombrados_a_zip(
                carpeta, 'retencion', parsear_retencion_xml)
            if limpiar:
                shutil.rmtree(carpeta, ignore_errors=True)
            stats['retenciones'] = {'copiados': copiados, 'sin_pdf': sin_pdf, 'errores': errores}
            if zip_bytes:
                ret_b64 = base64.b64encode(zip_bytes).decode()
            else:
                adv.append('No se encontraron PDFs de retenciones para renombrar.')
        else:
            adv.append('No se encontraron XMLs de retenciones.')

    return {
        'facturas_zip_b64':    fac_b64,
        'retenciones_zip_b64': ret_b64,
        'stats':               stats,
        'advertencias':        adv,
    }


def limpiar_tmp():
    """Elimina el directorio temporal de trabajo."""
    shutil.rmtree(_TMP, ignore_errors=True)
