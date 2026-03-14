"""
comparadores/comparar_retenciones.py
Comparación de dos vías para retenciones de IVA e IR:
  1) XMLs de comprobantes de retención descargados del portal SRI
  2) Ventas_Personalizado.xlsx (ventas con retenciones registradas en el sistema)

Clave de cruce: número de la factura de venta que origina la retención.
  XML:    campo NO_FAC_SUSTENTO (normalizado a formato 001-001-XXXXXXXXX)
  Excel:  campo NO_DOCUMENTO

Resultado:
  en_ambos    = xml ∩ sistema  (retenciones verificadas en ambas fuentes)
  sin_sistema = xml - sistema  (hay XML pero el sistema no lo registra)
  sin_xml     = sistema - xml  (sistema registra retención sin XML de respaldo)
"""
import pandas as pd


def comparar_retenciones(df_ret_xml, df_vp):
    """
    Compara los XMLs de retenciones contra Ventas_Personalizado.

    Args:
        df_ret_xml (pd.DataFrame): Retenciones parseadas de los XMLs.
        df_vp (pd.DataFrame): DataFrame de Ventas_Personalizado con columnas
                              NO_DOCUMENTO, RET_IVA_SIS, RET_IR_SIS, NO_RETENCION.

    Returns:
        dict con:
          'coincidencias'  — retenciones en ambas fuentes (con columnas Dif. IVA / Dif. IR)
          'sin_sistema'    — XMLs sin registro en Ventas_Personalizado
          'sin_xml'        — ventas con retención en sistema pero sin XML descargado
          'stats'          — dict con conteos para el resumen
    """
    resultado_vacio = {
        'coincidencias': pd.DataFrame(),
        'sin_sistema':   pd.DataFrame(),
        'sin_xml':       pd.DataFrame(),
        'stats': {},
    }
    if df_ret_xml.empty and df_vp.empty:
        return resultado_vacio

    df_ret = df_ret_xml.copy() if not df_ret_xml.empty else pd.DataFrame()
    df_v   = df_vp.copy()      if not df_vp.empty      else pd.DataFrame()

    # Clave en XMLs: número de la factura sustentada
    if not df_ret.empty and 'NO_FAC_SUSTENTO' in df_ret.columns:
        df_ret['CLAVE'] = df_ret['NO_FAC_SUSTENTO'].astype(str).str.strip()

    # Conjuntos de claves
    claves_xml = (set(df_ret['CLAVE'].dropna())
                  if not df_ret.empty and 'CLAVE' in df_ret.columns else set())
    claves_vp  = (set(df_v['NO_DOCUMENTO'].astype(str).str.strip().dropna())
                  if not df_v.empty and 'NO_DOCUMENTO' in df_v.columns else set())

    en_ambos    = claves_xml & claves_vp
    sin_sistema = claves_xml - claves_vp
    sin_xml     = claves_vp  - claves_xml

    if not df_ret.empty and not df_v.empty and 'NO_DOCUMENTO' in df_v.columns:
        df_v_m = df_v.rename(columns={'NO_DOCUMENTO': 'CLAVE'})
        cols_vp = ['CLAVE'] + [c for c in ('RET_IVA_SIS', 'RET_IR_SIS', 'NO_RETENCION')
                               if c in df_v_m.columns]
        df_v_m = df_v_m[cols_vp].rename(columns={'NO_RETENCION': 'NO_RET_SIS'})

        merged = df_ret.merge(df_v_m, on='CLAVE', how='left')

        # Asegurar tipos numéricos para calcular diferencias
        for col in ('RET_IVA_XML', 'RET_IR_XML', 'RET_IVA_SIS', 'RET_IR_SIS'):
            if col in merged.columns:
                merged[col] = pd.to_numeric(merged[col], errors='coerce').fillna(0)

        if 'RET_IVA_XML' in merged.columns:
            merged['DIF_IVA'] = merged['RET_IVA_XML'] - merged.get('RET_IVA_SIS', 0)
        if 'RET_IR_XML' in merged.columns:
            merged['DIF_IR']  = merged['RET_IR_XML']  - merged.get('RET_IR_SIS',  0)

        coincidencias = merged[merged['CLAVE'].isin(en_ambos)].rename(columns={
            'CLAVE':            'N° Factura Sustento',
            'SERIE_RETENCION':  'Serie Retención XML',
            'NO_RET_SIS':       'N° Ret. en Sistema',
            'RET_IVA_XML':      'Ret. IVA (XML)',
            'RET_IVA_SIS':      'Ret. IVA (Sistema)',
            'DIF_IVA':          'Dif. IVA',
            'RET_IR_XML':       'Ret. IR (XML)',
            'RET_IR_SIS':       'Ret. IR (Sistema)',
            'DIF_IR':           'Dif. IR',
            'RAZON_SOCIAL_RET': 'Razón Social (quien retiene)',
            'FECHA_RETENCION':  'Fecha Retención',
            'IMPORTE_FAC':      'Importe Factura',
        })
        sin_sis_df = df_ret[df_ret['CLAVE'].isin(sin_sistema)].rename(columns={
            'CLAVE':           'N° Factura Sustento',
            'SERIE_RETENCION': 'Serie Retención',
            'RET_IVA_XML':     'Ret. IVA',
            'RET_IR_XML':      'Ret. IR',
            'IMPORTE_FAC':     'Importe Factura',
        })
        sin_xml_df = df_v[
            df_v['NO_DOCUMENTO'].astype(str).str.strip().isin(sin_xml)
        ].rename(columns={
            'NO_DOCUMENTO':  'N° Factura Venta',
            'RAZON_SOCIAL':  'Razón Social Cliente',
            'FECHA_EMISION': 'Fecha Emisión',
            'NO_RETENCION':  'N° Retención en Sistema',
            'RET_IVA_SIS':   'Ret. IVA registrada',
            'RET_IR_SIS':    'Ret. IR registrada',
            'TOTAL':         'Total Factura',
        })
    else:
        coincidencias = sin_sis_df = sin_xml_df = pd.DataFrame()

    stats = {
        'ret_xml':    len(claves_xml),
        'vp_con_ret': len(claves_vp),
        'en_ambos':   len(en_ambos),
        'sin_sistema': len(sin_sistema),
        'sin_xml':    len(sin_xml),
    }
    return {
        'coincidencias': coincidencias,
        'sin_sistema':   sin_sis_df,
        'sin_xml':       sin_xml_df,
        'stats':         stats,
    }
