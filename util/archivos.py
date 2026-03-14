"""
util/archivos.py
Utilidades para manejo de archivos: carga masiva de XMLs, renombrado de PDFs
y auto-detección de la estructura de carpetas del proyecto.
"""
import io
import os
import shutil
import tempfile
import zipfile

import pandas as pd

from util.validacion import (
    MAX_XML_FILES,
    MAX_XML_SIZE_MB,
    sanitizar_nombre_archivo,
    es_ruta_segura,
)


MAX_ZIP_MB             = 200   # tamaño máximo del archivo ZIP
MAX_ZIP_RATIO          = 100   # ratio comprimido/descomprimido (anti-ZIP-bomb)
MAX_ZIP_UNCOMPRESSED_MB = 500  # contenido total descomprimido máximo


def _get_logger():
    """Devuelve el logger singleton si está disponible, o None."""
    try:
        from util.logger import obtener_logger
        return obtener_logger()
    except Exception:
        return None


def extraer_zip_a_temp(zip_path: str) -> str:
    """
    Extrae un ZIP a un directorio temporal (solo .xml y .pdf, aplanando subdirectorios).
    Aplica defensas anti-ZIP-bomb.

    El LLAMADOR es responsable de eliminar el directorio con shutil.rmtree().

    Args:
        zip_path (str): Ruta al archivo .zip.

    Returns:
        str: Ruta del directorio temporal con los archivos extraídos.

    Raises:
        ValueError: Si el ZIP es inválido, sospechoso o demasiado grande.
    """
    log = _get_logger()

    if not zip_path or not os.path.isfile(zip_path):
        raise ValueError(f"Archivo ZIP no encontrado: '{zip_path}'")
    if not zip_path.lower().endswith('.zip'):
        raise ValueError(f"Se esperaba un archivo .zip: '{os.path.basename(zip_path)}'")

    size_mb = os.path.getsize(zip_path) / 1_048_576
    if size_mb > MAX_ZIP_MB:
        raise ValueError(
            f"ZIP demasiado grande ({size_mb:.0f} MB). Máximo permitido: {MAX_ZIP_MB} MB.")

    tmpdir = tempfile.mkdtemp(prefix="voithos_")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Verificar ratio antes de extraer (anti-ZIP-bomb)
            compressed   = max(os.path.getsize(zip_path), 1)
            total_uncomp = sum(m.file_size for m in zf.infolist())
            ratio        = total_uncomp / compressed
            if ratio > MAX_ZIP_RATIO:
                raise ValueError(
                    f"ZIP sospechoso (ratio {ratio:.0f}x) — posible ZIP bomb. No se procesará.")
            uncomp_mb = total_uncomp / 1_048_576
            if uncomp_mb > MAX_ZIP_UNCOMPRESSED_MB:
                raise ValueError(
                    f"Contenido descomprimido demasiado grande ({uncomp_mb:.0f} MB). "
                    f"Máximo: {MAX_ZIP_UNCOMPRESSED_MB} MB.")

            extraidos = 0
            for member in zf.infolist():
                # Ignorar entradas de directorio
                if member.filename.endswith('/') or member.filename.endswith('\\'):
                    continue
                # Aplanar subdirectorios — solo el nombre base
                safe_name = os.path.basename(member.filename)
                if not safe_name:
                    continue
                ext = os.path.splitext(safe_name)[1].lower()
                if ext not in ('.xml', '.pdf'):
                    continue  # solo XML y PDF
                dest = os.path.join(tmpdir, safe_name)
                if not es_ruta_segura(tmpdir, dest):
                    continue
                with zf.open(member) as src, open(dest, 'wb') as dst:
                    dst.write(src.read())
                extraidos += 1

        print(f"   ✓  ZIP extraído: {extraidos} archivos (XML + PDF)")
        if log:
            log.info("ZIP extraído '%s': %d archivos", os.path.basename(zip_path), extraidos)
        return tmpdir

    except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise ValueError(f"ZIP inválido o corrupto: {e}") from e
    except ValueError:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise ValueError(f"Error al extraer ZIP: {e}") from e


def pdfs_renombrados_a_zip(carpeta_src: str, tipo: str, parser) -> tuple:
    """
    Lee los PDFs de carpeta_src, los renombra usando el XML correspondiente
    y los empaqueta en un ZIP en memoria.

    Args:
        carpeta_src (str): Carpeta (ya extraída) con XMLs + PDFs.
        tipo (str): 'factura' o 'retencion'.
        parser (callable): Parser XML.

    Returns:
        tuple: (zip_bytes: bytes | None, copiados: int, sin_pdf: int, errores: int)
               zip_bytes es None si no hay ningún PDF para empaquetar.
    """
    log = _get_logger()

    if not carpeta_src or not os.path.isdir(carpeta_src):
        return None, 0, 0, 1

    copiados = sin_pdf = errores = 0
    nombres_usados: set = set()
    archivos_zip: list  = []   # lista de (nombre_destino, bytes_pdf)

    try:
        xmls = [f for f in os.listdir(carpeta_src) if f.lower().endswith('.xml')]
    except OSError as e:
        print(f"   ❌  Error al leer carpeta: {e}")
        return None, 0, 0, 1

    for xml_file in xmls:
        datos = parser(os.path.join(carpeta_src, xml_file))
        if '_ERROR' in datos:
            errores += 1
            continue

        nombre_base = os.path.splitext(xml_file)[0]
        pdf_src = None
        for ext in ('.pdf', '.PDF'):
            candidato = os.path.join(carpeta_src, nombre_base + ext)
            if os.path.exists(candidato):
                pdf_src = candidato
                break

        if pdf_src is None:
            sin_pdf += 1
            continue

        campo_serie = 'SERIE' if tipo == 'factura' else 'SERIE_RETENCION'
        serie_raw   = str(datos.get(campo_serie, nombre_base))
        serie       = sanitizar_nombre_archivo(serie_raw) or sanitizar_nombre_archivo(nombre_base)

        nombre_dst = f"{serie}.pdf"
        # Resolver colisiones de nombre dentro del ZIP
        if nombre_dst in nombres_usados:
            base_d, ext_d = os.path.splitext(nombre_dst)
            sufijo = 2
            while nombre_dst in nombres_usados and sufijo < 100:
                nombre_dst = f"{base_d}_{sufijo}{ext_d}"
                sufijo += 1

        nombres_usados.add(nombre_dst)

        try:
            with open(pdf_src, 'rb') as f:
                pdf_bytes = f.read()
            archivos_zip.append((nombre_dst, pdf_bytes))
            copiados += 1
        except OSError as e:
            msg = f"No se pudo leer '{os.path.basename(pdf_src)}': {e}"
            print(f"   ⚠  {msg}")
            if log:
                log.warning("pdfs_renombrados_a_zip: %s", msg)
            errores += 1

    if not archivos_zip:
        return None, copiados, sin_pdf, errores

    # Empaquetar en ZIP en memoria
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in archivos_zip:
            zf.writestr(nombre, contenido)

    return buf.getvalue(), copiados, sin_pdf, errores


def cargar_xmls_carpeta(carpeta, parser, progress_callback=None):
    """
    Recorre una carpeta, aplica el parser a cada archivo .xml y devuelve
    un DataFrame con todos los registros válidos.

    Defensas implementadas:
    - Verifica que la ruta sea una carpeta existente antes de intentar listar.
    - Omite archivos que superen MAX_XML_SIZE_MB.
    - Limita el número de archivos a MAX_XML_FILES.
    - Continúa procesando aunque algunos archivos fallen.
    - Registra errores en el logger sin detener el procesamiento.

    Args:
        carpeta (str): Ruta de la carpeta con los XMLs.
        parser (callable): Función que recibe una ruta y devuelve un dict.
                           Si el dict contiene '_ERROR', el archivo se omite.
        progress_callback (callable | None): Función opcional (i, total) para
                           reportar progreso. Se llama cada 25 archivos.

    Returns:
        pd.DataFrame: Registros parseados. DataFrame vacío si no hay ninguno.
    """
    log = _get_logger()

    # ── Validación de entrada ─────────────────────────────────────────────────
    if not carpeta or not os.path.isdir(carpeta):
        msg = f"cargar_xmls_carpeta: ruta inválida o no es una carpeta: '{carpeta}'"
        print(f"   ❌  {msg}")
        if log:
            log.error(msg)
        return pd.DataFrame()

    # ── Descubrir archivos XML ────────────────────────────────────────────────
    try:
        todos = [f for f in os.listdir(carpeta) if f.lower().endswith('.xml')]
    except OSError as e:
        msg = f"Error al leer la carpeta '{os.path.basename(carpeta)}': {e}"
        print(f"   ❌  {msg}")
        if log:
            log.error(msg)
        return pd.DataFrame()

    if not todos:
        print(f"   ⚠  No se encontraron archivos .xml en '{os.path.basename(carpeta)}'")
        return pd.DataFrame()

    if len(todos) > MAX_XML_FILES:
        print(f"   ⚠  {len(todos)} XMLs encontrados — se procesarán solo los primeros {MAX_XML_FILES}")
        if log:
            log.warning("Carpeta '%s': %d XMLs encontrados, limitado a %d",
                        os.path.basename(carpeta), len(todos), MAX_XML_FILES)
        todos = todos[:MAX_XML_FILES]

    # ── Procesar archivos ─────────────────────────────────────────────────────
    resultados = []
    errores    = 0
    omitidos   = 0

    for i, archivo in enumerate(todos):
        # Feedback de progreso cada 25 archivos
        if progress_callback is not None and i % 25 == 0:
            try:
                progress_callback(i, len(todos))
            except Exception:
                pass

        path = os.path.join(carpeta, archivo)

        # Rechazo por tamaño
        try:
            size_mb = os.path.getsize(path) / 1_048_576
        except OSError:
            size_mb = 0

        if size_mb > MAX_XML_SIZE_MB:
            msg = (f"{archivo}: ignorado ({size_mb:.1f} MB > "
                   f"{MAX_XML_SIZE_MB} MB — ¿es un XML del SRI?)")
            print(f"   ⚠  {msg}")
            if log:
                log.warning(msg)
            omitidos += 1
            continue

        # Parsear
        resultado = parser(path)
        if '_ERROR' in resultado:
            nombre = resultado.get('_ARCHIVO', archivo)
            error  = resultado.get('_ERROR', 'error desconocido')
            print(f"   ⚠  {nombre}: {error}")
            if log:
                log.warning("XML omitido — %s: %s", nombre, error)
            errores += 1
        else:
            resultados.append(resultado)

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"   →  {len(todos)} XMLs en '{os.path.basename(carpeta)}'")
    if omitidos:
        print(f"   ⚠  {omitidos} archivo(s) ignorados por tamaño excesivo")
    if errores:
        print(f"   ⚠  {errores} archivo(s) con error omitidos")
    print(f"   ✓  {len(resultados)} registros cargados")

    return pd.DataFrame(resultados) if resultados else pd.DataFrame()


def copiar_pdfs_renombrados(carpeta_src, carpeta_dst, tipo, parser):
    """
    Copia los PDFs de carpeta_src a carpeta_dst renombrándolos con la
    serie del comprobante extraída del XML correspondiente.

    Defensas implementadas:
    - Valida que carpeta_src sea un directorio existente.
    - Sanitiza el nombre de destino para eliminar caracteres ilegales en Windows.
    - Detecta colisiones de nombre y avisa en lugar de sobrescribir silenciosamente.
    - Verifica path traversal antes de copiar.
    - Captura errores de copia por archivo sin detener el lote.

    Args:
        carpeta_src (str): Carpeta con XMLs y PDFs originales.
        carpeta_dst (str): Carpeta de destino para los PDFs renombrados.
        tipo (str): 'factura' o 'retencion'.
        parser (callable): Parser XML.

    Returns:
        tuple: (copiados, sin_pdf, errores)
    """
    log = _get_logger()

    if not carpeta_src or not os.path.isdir(carpeta_src):
        msg = f"copiar_pdfs: carpeta de origen inválida: '{carpeta_src}'"
        print(f"   ❌  {msg}")
        if log:
            log.error(msg)
        return 0, 0, 1

    try:
        os.makedirs(carpeta_dst, exist_ok=True)
    except OSError as e:
        msg = f"copiar_pdfs: no se pudo crear carpeta destino '{carpeta_dst}': {e}"
        print(f"   ❌  {msg}")
        if log:
            log.error(msg)
        return 0, 0, 1

    copiados = sin_pdf = errores = 0

    try:
        xmls = [f for f in os.listdir(carpeta_src) if f.lower().endswith('.xml')]
    except OSError as e:
        print(f"   ❌  Error al leer '{os.path.basename(carpeta_src)}': {e}")
        return 0, 0, 1

    for xml_file in xmls:
        datos = parser(os.path.join(carpeta_src, xml_file))
        if '_ERROR' in datos:
            errores += 1
            continue

        # Buscar el PDF con el mismo nombre base (insensible a mayúsculas en extensión)
        nombre_base = os.path.splitext(xml_file)[0]
        pdf_src = None
        for ext in ('.pdf', '.PDF'):
            candidato = os.path.join(carpeta_src, nombre_base + ext)
            if os.path.exists(candidato):
                pdf_src = candidato
                break

        if pdf_src is None:
            sin_pdf += 1
            continue

        # Obtener la serie y sanitizar para el sistema de archivos
        campo_serie = 'SERIE' if tipo == 'factura' else 'SERIE_RETENCION'
        serie_raw   = str(datos.get(campo_serie, nombre_base))
        serie       = sanitizar_nombre_archivo(serie_raw)

        if not serie:
            serie = sanitizar_nombre_archivo(nombre_base)

        dst_path = os.path.join(carpeta_dst, f"{serie}.pdf")

        # Verificar path traversal
        if not es_ruta_segura(carpeta_dst, dst_path):
            msg = f"copiar_pdfs: ruta de destino insegura para '{serie}' — omitido"
            print(f"   ⚠  {msg}")
            if log:
                log.warning(msg)
            errores += 1
            continue

        # Detectar colisión de nombre
        if os.path.exists(dst_path):
            # Intentar con sufijo numérico en lugar de sobrescribir silenciosamente
            base_dst, ext_dst = os.path.splitext(dst_path)
            sufijo = 2
            while os.path.exists(dst_path) and sufijo < 100:
                dst_path = f"{base_dst}_{sufijo}{ext_dst}"
                sufijo += 1
            if sufijo >= 100:
                print(f"   ⚠  Demasiadas colisiones de nombre para '{serie}' — omitido")
                errores += 1
                continue
            print(f"   ⚠  Colisión: '{serie}.pdf' ya existe — guardado como '{os.path.basename(dst_path)}'")

        try:
            shutil.copy2(pdf_src, dst_path)
            copiados += 1
        except OSError as e:
            msg = f"No se pudo copiar '{xml_file}': {e}"
            print(f"   ⚠  {msg}")
            if log:
                log.error("copiar_pdfs: %s", msg)
            errores += 1

    return copiados, sin_pdf, errores


def detectar_estructura(base):
    """
    Detecta automáticamente los archivos del proyecto a partir de una
    carpeta base, siguiendo las convenciones de nombres habituales.

    Convenciones detectadas:
      - Dirs con 'factura' o 'compra' → XMLs de facturas
      - Dirs con 'retencion'          → XMLs de retenciones
      - Dirs con 'sri' y 'txt'        → carpeta TXT del SRI
      - XLSX con 'personalizado'      → Ventas_Personalizado
      - XLSX con 'reporte','sistema','compras','ventas' → sistema contable
      - TXT cuya primera línea contiene 'ruc' o 'comprobante' → TXT SRI

    Args:
        base (str): Ruta de la carpeta raíz del proyecto.

    Returns:
        dict: Claves 'facturas', 'retenciones', 'sistema', 'ventas_pers',
              'sri_txt', 'data' (carpeta de salida).

    Raises:
        ValueError: Si la ruta no existe o no es una carpeta.
    """
    if not base or not str(base).strip():
        raise ValueError("La ruta proporcionada está vacía.")
    base = str(base).strip()
    if not os.path.exists(base):
        raise ValueError(f"La ruta no existe: '{base}'")
    if not os.path.isdir(base):
        raise ValueError(
            f"Se esperaba una CARPETA, no un archivo: '{os.path.basename(base)}'.\n"
            "Arrastra la carpeta del mes, no un archivo individual."
        )

    det = {
        'facturas':    None,
        'retenciones': None,
        'sistema':     None,
        'ventas_pers': None,
        'sri_txt':     None,
        'data':        os.path.join(base, 'processed_data'),
    }
    omitir = {'processed_data', '__pycache__', '.git', 'dist', 'build', 'logs'}

    try:
        entradas = list(os.scandir(base))
    except OSError as e:
        raise ValueError(f"No se pudo leer la carpeta '{os.path.basename(base)}': {e}") from e

    for entry in entradas:
        if entry.name.lower() in omitir:
            continue
        nombre = entry.name.lower()

        if entry.is_dir():
            # Las carpetas tienen prioridad sobre ZIPs del mismo tipo
            if any(k in nombre for k in ('factura', 'compra')):
                det['facturas'] = entry.path
            elif any(k in nombre for k in ('retencion', 'retention')):
                det['retenciones'] = entry.path
            elif 'sri' in nombre:
                # Carpeta "sri" o "sri_txt" → carpeta con TXT del SRI
                det['sri_txt'] = entry.path
            elif 'sistema' in nombre:
                # Carpeta "sistema" → buscar Excel adentro
                try:
                    for sub in os.scandir(entry.path):
                        sub_nom = sub.name.lower()
                        if sub.is_file() and sub_nom.endswith('.xlsx'):
                            if 'personalizado' in sub_nom:
                                det['ventas_pers'] = sub.path
                            elif any(k in sub_nom for k in ('reporte', 'compras', 'ventas', 'sistema')):
                                det['sistema'] = sub.path
                except OSError:
                    pass

        elif entry.is_file():
            if nombre.endswith('.zip'):
                # Solo usar ZIP si no se encontró carpeta con el mismo tipo
                if any(k in nombre for k in ('factura', 'compra')) and not det['facturas']:
                    det['facturas'] = entry.path
                elif any(k in nombre for k in ('retencion', 'retention')) and not det['retenciones']:
                    det['retenciones'] = entry.path
            elif nombre.endswith('.xlsx'):
                # Ignorar archivos que parezcan reportes generados por VOITHOS
                if any(nombre.startswith(p) for p in ('auditoria_', 'compras_', 'retenciones_', 'test_')):
                    continue
                if 'personalizado' in nombre:
                    det['ventas_pers'] = entry.path
                elif any(k in nombre for k in ('reporte', 'compras', 'ventas', 'sistema')):
                    det['sistema'] = entry.path
            elif nombre.endswith('.txt'):
                # Leer solo la primera línea para no consumir archivos grandes
                try:
                    size_mb = entry.stat().st_size / 1_048_576
                    if size_mb > 20:
                        continue  # TXT demasiado grande para ser del portal SRI
                    with open(entry.path, 'r', encoding='utf-8', errors='replace') as f:
                        primera_linea = f.readline().lower()
                    if 'ruc' in primera_linea or 'comprobante' in primera_linea:
                        det['sri_txt'] = entry.path
                except OSError:
                    pass

    return det
