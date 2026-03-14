"""
comparadores/comparar_compras.py
Comparación de tres vías para facturas de compra:
  1) XMLs descargados del portal SRI
  2) TXT de comprobantes recibidos (portal SRI)
  3) Sistema contable interno (Excel)

Clave de cruce: RUC_EMISOR + "|" + SERIE
  Ejemplo: "1791847652001|001-001-000005254"

Resultado de la comparación (lógica de conjuntos):
  en_todos        = xml ∩ txt ∩ sistema   (correctamente registrados en todo)
  no_en_sistema   = (xml ∪ txt) - sistema (hay en SRI pero no en el sistema)
  solo_en_sistema = sistema - (xml ∪ txt) (registrado sin respaldo en SRI)
"""
import pandas as pd


def comparar_compras(df_xml, df_txt, df_sys):
    """
    Compara los tres orígenes de datos de compras y clasifica los registros.

    Args:
        df_xml (pd.DataFrame): Facturas parseadas de los XMLs descargados.
        df_txt (pd.DataFrame): Comprobantes del TXT del SRI (ya con columna CLAVE).
        df_sys (pd.DataFrame): Compras del sistema contable (Excel).

    Returns:
        dict con:
          'coincidencias'    — facturas en los 3 orígenes (con columna Diferencia)
          'no_en_sistema'    — en SRI (XML o TXT) pero NO en el sistema
          'solo_en_sistema'  — en el sistema pero sin respaldo en SRI
          'stats'            — dict con conteos para el resumen
    """
    resultado_vacio = {
        'coincidencias':   pd.DataFrame(),
        'no_en_sistema':   pd.DataFrame(),
        'solo_en_sistema': pd.DataFrame(),
        'stats': {},
        'sistema': 0,
        'en_todos': 0,
    }
    if df_xml.empty and df_txt.empty and df_sys.empty:
        return resultado_vacio

    # Construir clave compuesta en df_xml si no existe
    if not df_xml.empty and 'RUC_EMISOR' in df_xml.columns and 'SERIE' in df_xml.columns:
        df_xml = df_xml.copy()
        df_xml['CLAVE'] = (df_xml['RUC_EMISOR'].astype(str).str.strip() + '|' +
                           df_xml['SERIE'].astype(str).str.strip())

    # Construir clave compuesta en df_sys si no existe
    if not df_sys.empty:
        df_sys = df_sys.copy()
        if ('CLAVE' not in df_sys.columns and
                'RUC_EMISOR' in df_sys.columns and 'SERIE' in df_sys.columns):
            df_sys['CLAVE'] = (df_sys['RUC_EMISOR'].astype(str).str.strip() + '|' +
                               df_sys['SERIE'].astype(str).str.strip())

    # Conjuntos de claves por origen
    claves_xml = (set(df_xml['CLAVE'].dropna())
                  if not df_xml.empty and 'CLAVE' in df_xml.columns else set())
    claves_txt = (set(df_txt['CLAVE'].dropna())
                  if not df_txt.empty and 'CLAVE' in df_txt.columns else set())
    claves_sys = (set(df_sys['CLAVE'].dropna())
                  if not df_sys.empty and 'CLAVE' in df_sys.columns else set())

    en_todos        = claves_xml & claves_txt & claves_sys
    no_en_sistema   = (claves_xml | claves_txt) - claves_sys
    solo_en_sistema = claves_sys - (claves_xml | claves_txt)

    # Merge para calcular diferencias de monto
    if not df_xml.empty and not df_sys.empty and 'CLAVE' in df_sys.columns:
        cols_sys = ['CLAVE'] + [c for c in ('SUBTOTAL', 'IVA_GASTO', 'TOTAL')
                                if c in df_sys.columns]
        df_sys_r = df_sys[cols_sys].rename(columns={
            'SUBTOTAL': 'SUBTOTAL_SIS',
            'IVA_GASTO': 'IVA_SIS',
            'TOTAL': 'TOTAL_SIS',
        })
        merged = df_xml.merge(df_sys_r, on='CLAVE', how='left')
        if 'TOTAL_SIS' not in merged.columns:
            merged['TOTAL_SIS'] = 0.0
        if 'TOTAL' not in merged.columns:
            merged['TOTAL'] = 0.0
        merged['TOTAL_SIS'] = pd.to_numeric(merged['TOTAL_SIS'], errors='coerce').fillna(0)
        merged['TOTAL']     = pd.to_numeric(merged['TOTAL'],     errors='coerce').fillna(0)
        merged['DIF_TOTAL'] = merged['TOTAL'] - merged['TOTAL_SIS']

        coincidencias = merged[merged['CLAVE'].isin(en_todos)].rename(columns={
            'RUC_EMISOR':   'RUC Emisor',
            'RAZON_SOCIAL': 'Razón Social',
            'SERIE':        'Serie',
            'FECHA':        'Fecha Emisión',
            'TOTAL':        'Total XML',
            'TOTAL_SIS':    'Total Sistema',
            'DIF_TOTAL':    'Diferencia',
            'CLAVE_ACCESO': 'Clave Acceso',
        })

        # Facturas no en sistema: incluir tanto las del XML como las del TXT
        # (el merge solo cubre XMLs; las claves solo en TXT se añaden desde df_txt)
        no_en_sis_xml = merged[merged['CLAVE'].isin(no_en_sistema)]
        if not df_txt.empty and 'CLAVE' in df_txt.columns:
            claves_solo_txt = no_en_sistema - claves_xml
            no_en_sis_txt   = df_txt[df_txt['CLAVE'].isin(claves_solo_txt)].copy()
            no_en_sis_df    = pd.concat([no_en_sis_xml, no_en_sis_txt], ignore_index=True)
        else:
            no_en_sis_df = no_en_sis_xml

        solo_sis_df   = (df_sys[df_sys['CLAVE'].isin(solo_en_sistema)]
                         if 'CLAVE' in df_sys.columns else pd.DataFrame())
    else:
        coincidencias = no_en_sis_df = solo_sis_df = pd.DataFrame()

    stats = {
        'xml':             len(claves_xml),
        'sistema':         len(claves_sys),
        'txt':             len(claves_txt),
        'en_todos':        len(en_todos),
        'no_en_sistema':   len(no_en_sistema),
        'solo_en_sistema': len(solo_en_sistema),
    }
    return {
        'coincidencias':   coincidencias,
        'no_en_sistema':   no_en_sis_df,
        'solo_en_sistema': solo_sis_df,
        'stats':           stats,
        'sistema':         len(claves_sys),
        'en_todos':        len(en_todos),
    }
