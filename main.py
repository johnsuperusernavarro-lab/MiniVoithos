"""
main.py — Punto de entrada de VOITHOS

Modo GUI (por defecto):
    python main.py

Modo CLI con comandos:
    python main.py analizar          # Análisis completo (compras + retenciones)
    python main.py compras           # Solo comparar compras
    python main.py retenciones       # Solo comparar retenciones
    python main.py renombrar_pdfs    # Solo copiar y renombrar PDFs
    python main.py gui               # Abrir la interfaz gráfica explícitamente

Uso con carpeta específica:
    python main.py analizar --carpeta "C:/ruta/al/proyecto"
"""
import argparse
import os
import sys
from datetime import datetime

# Asegurar que la raíz del proyecto esté en sys.path
# (necesario cuando se compila con PyInstaller)
if getattr(sys, 'frozen', False):
    _RAIZ = os.path.dirname(sys.executable)
else:
    _RAIZ = os.path.dirname(os.path.abspath(__file__))

if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

# Silenciar errores de encoding en Windows sin abortar
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(errors='ignore')

import pandas as pd

from config import CARPETA_SALIDA, SUBCARPETA_COMPRAS, SUBCARPETA_RETENCIONES, VERSION
from util.archivos import (cargar_xmls_carpeta, copiar_pdfs_renombrados,
                            detectar_estructura)
from parsers.facturas_xml import parsear_factura_xml
from parsers.retenciones_xml import parsear_retencion_xml
from parsers.sri_txt import cargar_txt_sri
from loaders.sistema_excel import cargar_sistema
from loaders.ventas_personalizado import cargar_ventas_personalizado
from comparadores.comparar_compras import comparar_compras
from comparadores.comparar_retenciones import comparar_retenciones
from reportes.generar_excel import generar_reporte


# ── Helpers de CLI ─────────────────────────────────────────────────────────────

def _confirmar(mensaje):
    """Pregunta S/N al usuario. Retorna True si responde S."""
    return input(f'{mensaje} (S/N): ').strip().upper() == 'S'


def _pedir_ruta(nombre, detectado=None):
    """Solicita una ruta con valor por defecto."""
    if detectado:
        print(f'  Detectado: {detectado}')
    val = input('  Enter para confirmar, o escribe otra ruta: ').strip()
    resultado = val if val else detectado
    if resultado:
        print(f'\n  → {resultado}')
    return resultado


def _obtener_carpeta_base(carpeta_arg=None):
    """
    Resuelve la carpeta base del proyecto.
    Si se pasa --carpeta en la línea de comandos, la usa.
    En caso contrario, la solicita al usuario interactivamente.
    """
    if carpeta_arg:
        base = carpeta_arg
    else:
        base = input('\n  Carpeta del proyecto: ').strip().strip('"')

    if not os.path.isdir(base):
        print(f'\n  ERROR: Carpeta no encontrada: {base}')
        input('  Presiona ENTER para salir...')
        sys.exit(1)
    return base


def _mostrar_deteccion(det):
    """Muestra las rutas detectadas en la consola."""
    print(f"\n  {'Carpeta facturas':<24}: {det['facturas']    or '*** NO ENCONTRADA ***'}")
    print(f"  {'Carpeta retenciones':<24}: {det['retenciones'] or '*** NO ENCONTRADA ***'}")
    print(f"  {'Sistema (Excel)':<24}: {det['sistema']     or '*** NO ENCONTRADO ***'}")
    print(f"  {'Ventas Personalizado':<24}: {det['ventas_pers'] or '---'}")
    print(f"  {'TXT SRI':<24}: {det['sri_txt']     or '---'}")
    print(f"  {'Salida':<24}: {det['data']}")


def _cargar_todos(det):
    """Carga todos los datos según las rutas detectadas."""
    df_fac = df_ret = df_comp = df_vp = df_txt = None

    if det.get('facturas'):
        print('\n  XMLs de facturas:')
        df_fac = cargar_xmls_carpeta(det['facturas'], parsear_factura_xml)

    if det.get('retenciones'):
        print('\n  XMLs de retenciones:')
        df_ret = cargar_xmls_carpeta(det['retenciones'], parsear_retencion_xml)

    if det.get('sistema'):
        print('\n  Sistema contable:')
        df_comp, _ = cargar_sistema(det['sistema'])

    if det.get('ventas_pers'):
        print('\n  Ventas Personalizado:')
        df_vp = cargar_ventas_personalizado(det['ventas_pers'])

    if det.get('sri_txt'):
        print('\n  TXT del SRI:')
        df_txt = cargar_txt_sri(det['sri_txt'])

    return df_fac, df_ret, df_comp, df_vp, df_txt


def _mostrar_resumen(stats_c, stats_r):
    """Imprime el resumen final en consola."""
    print('\n  RESUMEN FINAL\n')
    print('  COMPRAS')
    for lbl, k in [('XMLs descargados',         'xml'),
                   ('En Sistema',               'sistema'),
                   ('En TXT SRI',               'txt'),
                   ('Coinciden en los 3',       'en_todos'),
                   ('En SRI pero NO en Sistema','no_en_sistema'),
                   ('Solo en Sistema',          'solo_en_sistema')]:
        print(f'  {lbl:<42} {stats_c.get(k, 0)}')

    print('\n  RETENCIONES')
    for lbl, k in [('XMLs de retención',        'ret_xml'),
                   ('En Ventas Personalizado',   'vp_con_ret'),
                   ('Coinciden',                'en_ambos'),
                   ('XML sin Sistema',          'sin_sistema'),
                   ('Sistema sin XML',          'sin_xml')]:
        print(f'  {lbl:<42} {stats_r.get(k, 0)}')


# ── Comandos ───────────────────────────────────────────────────────────────────

def cmd_analizar(carpeta_arg=None):
    """Análisis completo: compras + retenciones + reporte Excel."""
    print('=' * 54)
    print(f'  VOITHOS v{VERSION}  —  Análisis Completo')
    print('=' * 54)

    base = _obtener_carpeta_base(carpeta_arg)
    print('\n  Detectando archivos...\n')
    det = detectar_estructura(base)
    _mostrar_deteccion(det)

    if not _confirmar('\n¿Los archivos detectados son correctos?'):
        print('\n  Ingresa las rutas manualmente:\n')
        det['facturas']    = _pedir_ruta('XMLs FACTURAS',         det['facturas'])
        det['retenciones'] = _pedir_ruta('XMLs RETENCIONES',      det['retenciones'])
        det['sistema']     = _pedir_ruta('SISTEMA (.xlsx)',        det['sistema'])
        det['ventas_pers'] = _pedir_ruta('VENTAS PERSONALIZADO',   det['ventas_pers'])
        det['sri_txt']     = _pedir_ruta('TXT SRI',               det['sri_txt'])

    os.makedirs(det['data'], exist_ok=True)

    # Copiar y renombrar PDFs
    print('\n  Copiando y renombrando PDFs...\n')
    if det.get('facturas'):
        dst = os.path.join(det['data'], SUBCARPETA_COMPRAS)
        print(f'  Compras → {dst}')
        c, s, e = copiar_pdfs_renombrados(
            det['facturas'], dst, 'factura', parsear_factura_xml)
        print(f'  Copiados: {c}  |  Sin PDF: {s}  |  Errores: {e}')

    if det.get('retenciones'):
        dst = os.path.join(det['data'], SUBCARPETA_RETENCIONES)
        print(f'\n  Retenciones → {dst}')
        c, s, e = copiar_pdfs_renombrados(
            det['retenciones'], dst, 'retencion', parsear_retencion_xml)
        print(f'  Copiados: {c}  |  Sin PDF: {s}  |  Errores: {e}')

    # Cargar datos
    print('\n  Cargando datos...\n')
    df_fac, df_ret, df_comp, df_vp, df_txt = _cargar_todos(det)

    # Comparar
    print('\n  Comparando...\n')
    compras_r = comparar_compras(
        df_fac  if df_fac  is not None else pd.DataFrame(),
        df_txt  if df_txt  is not None else pd.DataFrame(),
        df_comp if df_comp is not None else pd.DataFrame(),
    )
    ret_r = comparar_retenciones(
        df_ret if df_ret is not None else pd.DataFrame(),
        df_vp  if df_vp  is not None else pd.DataFrame(),
    )

    # Generar reporte
    print('\n  Generando reporte Excel...\n')
    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(det['data'], f'AUDITORIA_{ts}.xlsx')
    generar_reporte(compras_r, ret_r, out_path)

    _mostrar_resumen(compras_r.get('stats', {}), ret_r.get('stats', {}))
    print(f'\n  Reporte en: {out_path}')
    print('=' * 54)
    input('  Presiona ENTER para salir...')


def cmd_compras(carpeta_arg=None):
    """Solo comparación de compras (sin retenciones)."""
    print('=' * 54)
    print(f'  VOITHOS v{VERSION}  —  Análisis de Compras')
    print('=' * 54)

    base = _obtener_carpeta_base(carpeta_arg)
    det  = detectar_estructura(base)
    _mostrar_deteccion(det)
    os.makedirs(det['data'], exist_ok=True)

    print('\n  Cargando datos...\n')
    df_fac  = (cargar_xmls_carpeta(det['facturas'], parsear_factura_xml)
               if det.get('facturas') else pd.DataFrame())
    df_comp, _ = (cargar_sistema(det['sistema'])
                  if det.get('sistema') else (pd.DataFrame(), None))
    df_txt  = (cargar_txt_sri(det['sri_txt'])
               if det.get('sri_txt') else pd.DataFrame())

    print('\n  Comparando compras...\n')
    resultado = comparar_compras(df_fac, df_txt, df_comp)

    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(det['data'], f'COMPRAS_{ts}.xlsx')
    generar_reporte(resultado, {'stats': {}}, out_path)

    stats = resultado.get('stats', {})
    print(f"\n  En SRI pero NO en Sistema : {stats.get('no_en_sistema',   0)}")
    print(f"  Solo en Sistema           : {stats.get('solo_en_sistema', 0)}")
    print(f"\n  Reporte en: {out_path}")
    input('  Presiona ENTER para salir...')


def cmd_retenciones(carpeta_arg=None):
    """Solo comparación de retenciones (sin compras)."""
    print('=' * 54)
    print(f'  VOITHOS v{VERSION}  —  Análisis de Retenciones')
    print('=' * 54)

    base = _obtener_carpeta_base(carpeta_arg)
    det  = detectar_estructura(base)
    _mostrar_deteccion(det)
    os.makedirs(det['data'], exist_ok=True)

    print('\n  Cargando datos...\n')
    df_ret = (cargar_xmls_carpeta(det['retenciones'], parsear_retencion_xml)
              if det.get('retenciones') else pd.DataFrame())
    df_vp  = (cargar_ventas_personalizado(det['ventas_pers'])
              if det.get('ventas_pers') else pd.DataFrame())

    print('\n  Comparando retenciones...\n')
    resultado = comparar_retenciones(df_ret, df_vp)

    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(det['data'], f'RETENCIONES_{ts}.xlsx')
    generar_reporte({'stats': {}}, resultado, out_path)

    stats = resultado.get('stats', {})
    print(f"\n  XML sin registro en Sistema : {stats.get('sin_sistema', 0)}")
    print(f"  Sistema sin XML             : {stats.get('sin_xml',     0)}")
    print(f"\n  Reporte en: {out_path}")
    input('  Presiona ENTER para salir...')


def cmd_renombrar_pdfs(carpeta_arg=None):
    """Solo copia y renombra PDFs usando los XMLs como fuente de nombres."""
    print('=' * 54)
    print(f'  VOITHOS v{VERSION}  —  Renombrar PDFs')
    print('=' * 54)

    base = _obtener_carpeta_base(carpeta_arg)
    det  = detectar_estructura(base)
    _mostrar_deteccion(det)
    os.makedirs(det['data'], exist_ok=True)

    if det.get('facturas'):
        dst = os.path.join(det['data'], SUBCARPETA_COMPRAS)
        print(f'\n  Compras → {dst}')
        c, s, e = copiar_pdfs_renombrados(
            det['facturas'], dst, 'factura', parsear_factura_xml)
        print(f'  Copiados: {c}  |  Sin PDF: {s}  |  Errores: {e}')

    if det.get('retenciones'):
        dst = os.path.join(det['data'], SUBCARPETA_RETENCIONES)
        print(f'\n  Retenciones → {dst}')
        c, s, e = copiar_pdfs_renombrados(
            det['retenciones'], dst, 'retencion', parsear_retencion_xml)
        print(f'  Copiados: {c}  |  Sin PDF: {s}  |  Errores: {e}')

    print('\n  PDFs renombrados correctamente.')
    input('  Presiona ENTER para salir...')


def cmd_gui():
    """Abre la interfaz gráfica."""
    from gui.gui_app import main as gui_main
    gui_main()


# ── Despacho de argumentos ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog='voithos',
        description=f'VOITHOS v{VERSION} — Auditor Contable SRI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comandos disponibles:
  analizar        Análisis completo: compras + retenciones + reporte Excel
  compras         Solo comparar facturas de compra
  retenciones     Solo comparar retenciones de IVA e IR
  renombrar_pdfs  Solo copiar y renombrar PDFs
  gui             Abrir la interfaz gráfica (también es el modo por defecto)

Ejemplos:
  python main.py
  python main.py analizar
  python main.py analizar --carpeta "C:/datos/enero_2026"
  python main.py compras --carpeta "C:/datos/enero_2026"
        """,
    )
    parser.add_argument(
        'comando',
        nargs='?',
        default='gui',
        choices=['analizar', 'compras', 'retenciones', 'renombrar_pdfs', 'gui'],
        help='Comando a ejecutar (por defecto: gui)',
    )
    parser.add_argument(
        '--carpeta',
        metavar='RUTA',
        help='Carpeta del proyecto (omitir para que el programa la solicite)',
    )

    args = parser.parse_args()

    mapa_comandos = {
        'analizar':       lambda: cmd_analizar(args.carpeta),
        'compras':        lambda: cmd_compras(args.carpeta),
        'retenciones':    lambda: cmd_retenciones(args.carpeta),
        'renombrar_pdfs': lambda: cmd_renombrar_pdfs(args.carpeta),
        'gui':            cmd_gui,
    }

    try:
        mapa_comandos[args.comando]()
    except KeyboardInterrupt:
        print('\n\nCancelado por el usuario.')
    except Exception as e:
        print(f'\n  ERROR inesperado: {e}')
        input('  Presiona ENTER para salir...')
        sys.exit(1)


if __name__ == '__main__':
    main()
