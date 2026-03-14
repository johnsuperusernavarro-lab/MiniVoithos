"""
util/logger.py
Logger persistente en disco para VOITHOS.

Los errores de procesamiento (XML corruptos, filas inválidas, etc.) se
registran en un archivo de log diario sin detener el programa.
La GUI captura print() con _BufferWriter; este logger escribe en disco
para que el usuario pueda adjuntar el log al reportar un bug.

Uso:
    from util.logger import obtener_logger
    log = obtener_logger()          # singleton — devuelve el mismo logger
    log.warning("XML omitido: %s", nombre_archivo)
    log.error("Fallo al leer Excel: %s", exc)
"""
import logging
import os
from datetime import datetime

_instancia = None


def obtener_logger(carpeta_salida=None):
    """
    Devuelve el logger de VOITHOS (singleton).

    La primera llamada con carpeta_salida configura el archivo de log en
    carpeta_salida/logs/voithos_YYYYMMDD.log.
    Llamadas posteriores (con o sin argumento) devuelven el mismo logger.

    Args:
        carpeta_salida (str | None): Carpeta donde crear la subcarpeta logs/.
                                     Si es None, solo se loguea a consola.

    Returns:
        logging.Logger
    """
    global _instancia
    if _instancia is not None:
        return _instancia

    logger = logging.getLogger('voithos')
    logger.setLevel(logging.DEBUG)
    # Evitar propagar al root logger (evita duplicados)
    logger.propagate = False

    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(message)s',
        datefmt='%H:%M:%S'
    )

    # ── Handler de archivo ────────────────────────────────────────────────────
    if carpeta_salida:
        try:
            log_dir  = os.path.join(carpeta_salida, 'logs')
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, f"voithos_{datetime.now():%Y%m%d}.log")
            fh = logging.FileHandler(log_path, encoding='utf-8', mode='a')
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except Exception:
            # No crashear si no podemos escribir el log
            pass

    _instancia = logger
    return logger


def resetear_logger():
    """
    Resetea el singleton del logger.
    Útil en tests o si se cambia la carpeta de salida entre sesiones.
    """
    global _instancia
    if _instancia is not None:
        for handler in _instancia.handlers[:]:
            try:
                handler.close()
            except Exception:
                pass
            _instancia.removeHandler(handler)
    _instancia = None
