"""
parsers/sri_txt.py
Cargador del TXT de comprobantes recibidos exportado desde el portal del SRI.

Formato esperado: TSV (tab-separated), encoding latin-1, cabecera en fila 0.
Descarga: portal SRI → Comprobantes Recibidos → Exportar.

Acepta:
  - Un archivo .txt individual
  - Una carpeta con varios .txt mensuales (los concatena todos)

Defensas implementadas:
  - Detecta automáticamente el separador (tab, punto y coma, coma).
  - Prueba múltiples encodings antes de fallar.
  - Avisa si las columnas de RUC y serie no se encuentran.
  - Continúa aunque algunos archivos del lote fallen.
"""
import os

import pandas as pd

from util.normalizacion import formatear_num_documento

# Encodings a probar, en orden de probabilidad para archivos del SRI Ecuador
_ENCODINGS = ['latin-1', 'utf-8-sig', 'utf-8', 'cp1252', 'iso-8859-1']


def _detectar_separador(path):
    """
    Lee las primeras 4 KB del archivo para detectar el separador predominante.

    Returns:
        str: '\\t', ';' o ','
    """
    try:
        with open(path, 'rb') as f:
            muestra_bytes = f.read(4096)
        # Decodificar con latin-1 para no fallar en ningún byte
        muestra = muestra_bytes.decode('latin-1', errors='replace')
    except OSError:
        return '\t'  # asumir tab si no podemos leer

    tabs      = muestra.count('\t')
    puntocom  = muestra.count(';')
    comas     = muestra.count(',')

    if tabs >= puntocom and tabs >= comas:
        return '\t'
    if puntocom >= comas:
        return ';'
    return ','


def _leer_txt_tolerante(path, sep):
    """
    Intenta leer un archivo CSV/TSV probando varios encodings.

    Returns:
        pd.DataFrame o None si todos los encodings fallan.
    """
    for enc in _ENCODINGS:
        try:
            df = pd.read_csv(
                path, sep=sep, encoding=enc,
                header=0, dtype=str, on_bad_lines='warn',
            )
            return df
        except UnicodeDecodeError:
            continue
        except Exception:
            # Separador incorrecto u otro error — no reintentar con mismo sep
            break
    # Último recurso: latin-1 con reemplazo de caracteres inválidos
    try:
        return pd.read_csv(
            path, sep=sep, encoding='latin-1',
            errors='replace', header=0, dtype=str, on_bad_lines='skip',
        )
    except Exception:
        return None


def cargar_txt_sri(ruta):
    """
    Lee uno o varios TXT del SRI y los combina en un único DataFrame.

    Normaliza las columnas RUC_EMISOR y SERIE_COMPROBANTE para poder
    cruzarlos con los datos de los XMLs y el sistema contable.
    Deduplica por clave RUC|SERIE (se queda con el primer registro).

    Args:
        ruta (str): Ruta de un archivo .txt o de una carpeta con varios .txt.

    Returns:
        pd.DataFrame: Registros únicos del TXT. DataFrame vacío si falla.
    """
    if os.path.isdir(ruta):
        try:
            archivos = [
                os.path.join(ruta, f)
                for f in os.listdir(ruta) if f.lower().endswith('.txt')
            ]
        except OSError as e:
            print(f"   ❌  Error al leer carpeta TXT SRI: {e}")
            return pd.DataFrame()
        if not archivos:
            print("   ⚠  La carpeta TXT SRI no contiene archivos .txt")
            return pd.DataFrame()
    else:
        archivos = [ruta]

    dataframes = []
    for archivo in archivos:
        nombre = os.path.basename(archivo)

        # Detectar separador antes de intentar leer
        sep = _detectar_separador(archivo)
        if sep != '\t':
            print(f"   ⚠  {nombre}: separador detectado '{sep}' (se esperaba tabulación)")

        df_tmp = _leer_txt_tolerante(archivo, sep)
        if df_tmp is None:
            print(f"   ❌  No se pudo leer '{nombre}' con ningún encoding conocido")
            continue

        if df_tmp.empty or len(df_tmp.columns) <= 1:
            # Puede haber fallado la detección de separador; intentar con tab de todas formas
            if sep != '\t':
                df_tmp2 = _leer_txt_tolerante(archivo, '\t')
                if df_tmp2 is not None and len(df_tmp2.columns) > 1:
                    df_tmp = df_tmp2
                    print(f"   ℹ  {nombre}: re-leído con tabulación como separador")

        if df_tmp.empty:
            print(f"   ⚠  {nombre}: el archivo está vacío")
            continue

        dataframes.append(df_tmp)
        print(f"   ✓  {len(df_tmp)} registros en {nombre}")

    if not dataframes:
        print("   ⚠  No se pudo cargar ningún TXT del SRI")
        return pd.DataFrame()

    df = pd.concat(dataframes, ignore_index=True)

    # ── Detección flexible de columnas ────────────────────────────────────────
    # El portal SRI puede variar ligeramente el nombre de las columnas
    col_ruc = next(
        (c for c in df.columns if 'RUC' in str(c).upper()),
        None
    )
    # Preferir columnas que tengan "SERIE" en el nombre; como fallback aceptar
    # "COMPROBANTE" pero solo si NO es la columna de tipo ("TIPO_COMPROBANTE").
    col_serie = next(
        (c for c in df.columns if 'SERIE' in str(c).upper()),
        None
    )
    if col_serie is None:
        col_serie = next(
            (c for c in df.columns
             if 'COMPROBANTE' in str(c).upper()
             and 'TIPO' not in str(c).upper()),
            None
        )

    if not col_ruc:
        print("   ⚠  TXT SRI: no se encontró columna de RUC — "
              "¿el archivo es del portal SRI? La comparación de compras se omitirá.")
        return df

    if not col_serie:
        print("   ⚠  TXT SRI: no se encontró columna de serie/comprobante — "
              "La comparación de compras se omitirá.")
        return df

    # Filtrar solo facturas — el portal SRI exporta en un solo archivo
    # tanto facturas como retenciones y notas; solo las facturas son útiles aquí
    col_tipo = next(
        (c for c in df.columns if 'TIPO' in str(c).upper()),
        None
    )
    if col_tipo:
        antes_filtro = len(df)
        df = df[df[col_tipo].astype(str).str.strip().str.lower().str.startswith('factura')].copy()
        descartados = antes_filtro - len(df)
        if descartados:
            print(f"   ℹ  {descartados} registros no-Factura descartados del TXT SRI "
                  f"(retenciones, notas de crédito, etc.)")
        if df.empty:
            print("   ⚠  TXT SRI: no hay registros de tipo Factura tras el filtro")
            return df

    df['RUC_EMISOR']        = df[col_ruc].astype(str).str.strip()
    df['SERIE_COMPROBANTE'] = (
        df[col_serie].astype(str).str.strip()
        .apply(formatear_num_documento)
    )
    df['CLAVE'] = df['RUC_EMISOR'] + '|' + df['SERIE_COMPROBANTE']

    # El SRI puede emitir correcciones que generan duplicados;
    # nos quedamos con el primer registro (más antiguo)
    antes = len(df)
    df = df.groupby('CLAVE').first().reset_index()
    if len(df) < antes:
        print(f"   ℹ  {antes - len(df)} registros duplicados eliminados del TXT SRI")

    print(f"   ✓  {len(df)} registros únicos en TXT SRI")
    return df
