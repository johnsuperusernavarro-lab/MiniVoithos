"""
loaders/ventas_personalizado.py
Cargador del archivo Ventas_Personalizado.xlsx.

Este archivo auxiliar contiene las facturas de venta del contribuyente
que tienen retenciones registradas en el sistema contable. Se usa para
cruzar contra los XMLs de retenciones recibidos del portal SRI.

Columnas esperadas (acepta variaciones de nombre):
  FECHA_EMISION, NO_DOCUMENTO, RAZON_SOCIAL,
  RET_IVA_SIS, RET_IR_SIS, NO_RETENCION, SUBTOTAL, TOTAL, SALDO
"""
import os

import pandas as pd


# Mapeo flexible de nombres de columna: clave = nombre exacto esperado,
# valor = fragmentos que se buscan en el nombre real de la columna (en MAYÚSCULAS).
_MAPA_COLUMNAS = {
    'FECHA_EMISION': ['FECHA_EMISION', 'FECHA EMISION', 'FECHA DE EMISION', 'FECHA DE EMISIÓN'],
    'NO_DOCUMENTO':  ['NO_DOCUMENTO',  'NO DOCUMENTO',  '# DOCUMENTO', '#DOCUMENTO', 'DOCUMENTO'],
    'RAZON_SOCIAL':  ['RAZON_SOCIAL',  'RAZON SOCIAL',  'RAZÓN SOCIAL'],
    'RET_IVA_SIS':   ['RET_IVA_SIS',   'RET IVA',       'RETENCION IVA', 'RETENCIÓN IVA', 'RETENCIÓN_IVA'],
    'RET_IR_SIS':    ['RET_IR_SIS',    'RET IR',        'RETENCION IR',  'RETENCIÓN IR',  'RETENCIÓN_IR'],
    'NO_RETENCION':  ['NO_RETENCION',  'NO RETENCION',  '# RETENCION', '#RETENCION', '# RETENCIÓN'],
    'SUBTOTAL':      ['SUBTOTAL'],
    'TOTAL':         ['TOTAL'],
    'SALDO':         ['SALDO'],
}

_COLUMNAS_NUMERICAS = ('RET_IVA_SIS', 'RET_IR_SIS', 'SUBTOTAL', 'TOTAL', 'SALDO')

# Columnas mínimas para que la comparación tenga sentido
_COLUMNAS_CRITICAS = {'NO_DOCUMENTO', 'RET_IVA_SIS', 'RET_IR_SIS'}


def _a_numerico_seguro(serie, col):
    """
    Convierte una Serie a numérico tolerando formatos con símbolo de moneda,
    comas como separador de miles, y espacios.

    Avisa si hay valores que no pudieron convertirse.

    Args:
        serie (pd.Series): Serie a convertir.
        col (str): Nombre de la columna (solo para el mensaje de aviso).

    Returns:
        pd.Series: Serie numérica con 0 donde no se pudo convertir.
    """
    limpio = (serie.astype(str)
              .str.strip()
              .str.replace(r'[$,\s]', '', regex=True))
    resultado = pd.to_numeric(limpio, errors='coerce')
    n_fallidos = resultado.isna().sum()
    if n_fallidos > 0:
        print(f"   ⚠  {n_fallidos} valor(es) no numérico(s) en columna '{col}' — "
              "se usan como 0")
    return resultado.fillna(0)


def cargar_ventas_personalizado(path):
    """
    Lee el archivo Ventas_Personalizado.xlsx y normaliza sus columnas.

    Defensas implementadas:
    - Envuelve pd.read_excel en try/except con mensajes claros para el usuario.
    - Detecta y avisa si faltan columnas críticas para la comparación.
    - Usa _a_numerico_seguro para conversión de montos (tolera $, comas, espacios).
    - Avisa si no se reconoce ninguna columna esperada.

    Args:
        path (str): Ruta al archivo Excel de ventas personalizadas.

    Returns:
        pd.DataFrame: DataFrame con columnas normalizadas.

    Raises:
        ValueError: Con mensaje amigable si el archivo no se puede leer.
    """
    nombre = os.path.basename(path)

    # Detectar la fila de cabeceras: buscar la primera fila con ≥ 2 celdas
    # que coincidan con columnas esperadas. El archivo puede tener filas de
    # encabezado de empresa/fecha antes de los datos reales.
    header_row = 0
    try:
        import openpyxl
        wb_tmp = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws_tmp = wb_tmp.active
        for i, row in enumerate(ws_tmp.iter_rows(max_row=15, values_only=True)):
            celdas = [str(c).strip().upper() for c in row if c is not None]
            # Buscar indicadores de fila de cabecera
            indicadores = {'DOCUMENTO', 'RETENCION', 'RETENCIÓN', 'EMISIÓN',
                           'EMISION', 'TOTAL', 'SUBTOTAL', 'SOCIAL'}
            if sum(1 for c in celdas if any(ind in c for ind in indicadores)) >= 2:
                header_row = i
                break
        wb_tmp.close()
    except Exception:
        pass  # usar header_row=0 como fallback

    try:
        df = pd.read_excel(path, dtype=str, header=header_row)
    except FileNotFoundError:
        raise ValueError(
            f"No se encontró el archivo: '{nombre}'.\n"
            "Verifica que la ruta sea correcta."
        )
    except Exception as e:
        msg_lower = str(e).lower()
        if 'encrypted' in msg_lower or 'password' in msg_lower:
            raise ValueError(
                f"'{nombre}' está protegido con contraseña.\n"
                "En Excel: Revisar → Proteger libro → Quitar contraseña."
            ) from e
        if 'not a zip' in msg_lower or 'bad magic' in msg_lower:
            raise ValueError(
                f"'{nombre}' no es un archivo Excel válido.\n"
                "Si es un archivo .xls (formato antiguo), "
                "ábrelo en Excel y guárdalo como .xlsx."
            ) from e
        raise ValueError(
            f"No se pudo leer '{nombre}': {e}\n"
            "Verifica que el archivo no esté abierto en Excel y sea un .xlsx válido."
        ) from e

    if df.empty:
        print(f"   ⚠  '{nombre}' está vacío")
        return df

    # ── Renombrar columnas usando el mapa flexible ────────────────────────────
    renombrar = {}
    for col_real in df.columns:
        col_upper = str(col_real).upper().strip()
        for nombre_destino, variantes in _MAPA_COLUMNAS.items():
            if any(v in col_upper for v in variantes):
                renombrar[col_real] = nombre_destino
                break

    df = df.rename(columns=renombrar)

    # ── Verificar columnas reconocidas ────────────────────────────────────────
    cols_encontradas = set(renombrar.values())
    if not cols_encontradas:
        print(f"   ⚠  '{nombre}': no se reconoció ninguna columna esperada.\n"
              "   Columnas encontradas: " + ", ".join(str(c) for c in df.columns[:8]))

    cols_faltantes = _COLUMNAS_CRITICAS - set(df.columns)
    if cols_faltantes:
        print(f"   ⚠  '{nombre}': faltan columnas críticas para la comparación: "
              f"{', '.join(sorted(cols_faltantes))}\n"
              "   La comparación de retenciones puede ser incompleta.")

    # ── Convertir columnas numéricas ──────────────────────────────────────────
    for col in _COLUMNAS_NUMERICAS:
        if col in df.columns:
            df[col] = _a_numerico_seguro(df[col], col)

    print(f"   ✓  {len(df)} filas en Ventas_Personalizado")
    return df
