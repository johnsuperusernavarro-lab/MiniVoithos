# VOITHOS.spec — Configuración de PyInstaller
#
# Genera un ejecutable standalone con:
#   pyinstaller VOITHOS.spec
#
# El resultado estará en dist/VOITHOS/VOITHOS.exe
# Junto al .exe se crea automáticamente la carpeta processed_data/

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Incluir los datos de customtkinter (temas, fuentes)
        ('venv/Lib/site-packages/customtkinter', 'customtkinter'),
    ],
    hiddenimports=[
        'customtkinter',
        'tkinterdnd2',
        'openpyxl',
        'pandas',
        'xml.etree.ElementTree',
        # Módulos del proyecto
        'config',
        'util.normalizacion',
        'util.archivos',
        'util.validacion',
        'util.logger',
        'parsers.facturas_xml',
        'parsers.retenciones_xml',
        'parsers.sri_txt',
        'loaders.sistema_excel',
        'loaders.ventas_personalizado',
        'comparadores.comparar_compras',
        'comparadores.comparar_retenciones',
        'reportes.generar_excel',
        'gui.gui_app',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VOITHOS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Sin ventana de consola (GUI mode)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='gui/voithos.ico',   # Descomentar si tienes un icono
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VOITHOS',
)
