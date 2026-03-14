"""
voithos_web.py — Punto de entrada para la versión web (Pyodide).

El JavaScript escribe los archivos del usuario en el filesystem
virtual de Pyodide antes de llamar a analizar().

Rutas esperadas en /tmp/voithos/:
  facturas/         carpeta con .xml  (o facturas.zip)
  retenciones/      carpeta con .xml  (o retenciones.zip)
  sistema.xlsx      ReporteComprasVentas
  comprobantes.txt  TXT del portal SRI  (opcional)
  ventas.xlsx       Ventas_Personalizado (opcional)
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
from util.archivos import cargar_xmls_carpeta, extraer_zip_a_temp

_TMP = '/tmp/voithos'


def _resolver_carpeta_xmls(ruta_dir: str, ruta_zip: str):
    """Devuelve (carpeta, hay_que_limpiar). Prefiere carpeta sobre ZIP."""
    if os.path.isdir(ruta_dir):
        return ruta_dir, False
    if os.path.isfile(ruta_zip):
        tmpdir = extraer_zip_a_temp(ruta_zip)
        return tmpdir, True
    return None, False


def analizar(hay_facturas=False, hay_retenciones=False,
             hay_sistema=False, hay_txt=False, hay_vp=False):
    """
    Ejecuta el análisis completo y devuelve el reporte Excel en base64.

    Returns:
        dict: {
            'excel_b64':    str   — Excel codificado en base64,
            'stats_compras': dict,
            'stats_ret':     dict,
            'advertencias':  list[str],
        }
    Raises:
        ValueError: si el sistema contable no se puede leer.
    """
    advertencias = []

    # ── Facturas ──────────────────────────────────────────────────────────────
    df_fac = pd.DataFrame()
    if hay_facturas:
        carpeta, limpiar = _resolver_carpeta_xmls(
            os.path.join(_TMP, 'facturas'),
            os.path.join(_TMP, 'facturas.zip'),
        )
        if carpeta:
            df_fac = cargar_xmls_carpeta(carpeta, parsear_factura_xml)
            if limpiar:
                shutil.rmtree(carpeta, ignore_errors=True)
        else:
            advertencias.append('No se encontraron XMLs de facturas.')

    # ── Retenciones ───────────────────────────────────────────────────────────
    df_ret = pd.DataFrame()
    if hay_retenciones:
        carpeta, limpiar = _resolver_carpeta_xmls(
            os.path.join(_TMP, 'retenciones'),
            os.path.join(_TMP, 'retenciones.zip'),
        )
        if carpeta:
            df_ret = cargar_xmls_carpeta(carpeta, parsear_retencion_xml)
            if limpiar:
                shutil.rmtree(carpeta, ignore_errors=True)
        else:
            advertencias.append('No se encontraron XMLs de retenciones.')

    # ── Sistema contable ──────────────────────────────────────────────────────
    df_comp = pd.DataFrame()
    if hay_sistema:
        df_comp, _ = cargar_sistema(os.path.join(_TMP, 'sistema.xlsx'))

    # ── TXT del SRI (opcional) ────────────────────────────────────────────────
    df_txt = pd.DataFrame()
    if hay_txt:
        try:
            df_txt = cargar_txt_sri(os.path.join(_TMP, 'comprobantes.txt'))
        except Exception as e:
            advertencias.append(f'TXT SRI: {e}')

    # ── Ventas personalizado (opcional) ───────────────────────────────────────
    df_vp = pd.DataFrame()
    if hay_vp:
        try:
            df_vp = cargar_ventas_personalizado(os.path.join(_TMP, 'ventas.xlsx'))
        except ValueError as e:
            advertencias.append(str(e))

    # ── Comparar ──────────────────────────────────────────────────────────────
    compras_r = comparar_compras(df_fac, df_txt, df_comp)
    ret_r     = comparar_retenciones(df_ret, df_vp)

    # ── Generar reporte en memoria ────────────────────────────────────────────
    # openpyxl acepta BytesIO como destino igual que una ruta de archivo
    buf = io.BytesIO()
    generar_reporte(compras_r, ret_r, buf)

    return {
        'excel_b64':     base64.b64encode(buf.getvalue()).decode(),
        'stats_compras': compras_r.get('stats', {}),
        'stats_ret':     ret_r.get('stats', {}),
        'advertencias':  advertencias,
    }


def limpiar_tmp():
    """Elimina el directorio temporal de trabajo."""
    shutil.rmtree(_TMP, ignore_errors=True)
