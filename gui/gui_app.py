"""
gui/gui_app.py
Interfaz gráfica de VOITHOS — Rediseño UX con Catppuccin Mocha.

Arquitectura:
  - Sidebar fijo (210px) con navegación entre herramientas
  - Dashboard con 4 tarjetas de acción clara
  - Paneles individuales por herramienta con drag & drop
  - Vista de resultados con métricas visuales
  - Historial de sesión
  - Barra de estado con mensajes descriptivos

Dependencias:
    pip install customtkinter tkinterdnd2
"""

import os
import re
import shutil
import sys
import threading
import subprocess
from datetime import datetime

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

# ── Directorio raíz del programa ───────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    _RAIZ = os.path.dirname(sys.executable)
else:
    _RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

# ══════════════════════════════════════════════════════════════════════════════
#  PALETA CATPPUCCIN MOCHA
# ══════════════════════════════════════════════════════════════════════════════

CRUST    = "#11111b"   # sidebar
BASE     = "#1e1e2e"   # fondo principal
MANTLE   = "#181825"   # fondos secundarios / headers / drop zones
SURFACE0 = "#313244"   # tarjetas / cards
SURFACE1 = "#45475a"   # bordes, dividers
SURFACE2 = "#585b70"   # bordes hover / activos

TEXT     = "#cdd6f4"   # texto principal
SUBTEXT0 = "#a6adc8"   # subtítulos / placeholder
OVERLAY0 = "#6c7086"   # texto muted / deshabilitado

BLUE     = "#89b4fa"   # acento Auditoría mensual
GREEN    = "#a6e3a1"   # acento Compras
MAUVE    = "#cba6f7"   # acento Retenciones
PEACH    = "#fab387"   # acento Organizar PDFs
TEAL     = "#94e2d5"   # éxito / completado
RED      = "#f38ba8"   # alerta crítica
YELLOW   = "#f9e2af"   # advertencia


# ══════════════════════════════════════════════════════════════════════════════
#  CAPTURA DE STDOUT (thread-safe mediante lista buffer)
# ══════════════════════════════════════════════════════════════════════════════

class _BufferWriter:
    """
    Redirige sys.stdout a una lista durante el análisis.
    Captura todos los print() de los módulos de lógica para mostrarlos
    en el log de la vista de resultados.
    """
    def __init__(self, buf: list):
        self._buf = buf

    def write(self, text: str):
        self._buf.append(text)

    def flush(self):
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  APLICACIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class VoithosApp(TkinterDnD.Tk):
    """
    Ventana principal de VOITHOS.
    Layout: sidebar fijo (210px) | área de contenido dinámica
                                 | barra de estado (32px)
    """

    # ── Inicialización ─────────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("VOITHOS — Auditor Contable SRI")
        self.geometry("980x700")
        self.minsize(820, 580)
        self.configure(bg=BASE)

        # Estado de la sesión
        self._historial:   list = []     # [{tipo, ts, stats_c, stats_r, path}]
        self._nav_btns:    dict = {}     # {vista_id: CTkButton}
        self._analysis_id: int  = 0     # invalida resultados de análisis anteriores
        self._saved:       dict = {      # rutas persistidas entre navegaciones
            "auditoria":   {},
            "compras":     {},
            "retenciones": {},
            "pdfs":        {},
        }

        self._build_shell()
        self._navigate("dashboard")

    # ── Shell ──────────────────────────────────────────────────────────────────

    def _build_shell(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Sidebar
        self._sidebar = ctk.CTkFrame(self, fg_color=CRUST, corner_radius=0, width=210)
        self._sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        self._sidebar.grid_propagate(False)
        self._build_sidebar()

        # Área de contenido
        self._content = ctk.CTkFrame(self, fg_color=BASE, corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.columnconfigure(0, weight=1)
        self._content.rowconfigure(0, weight=1)

        # Barra de estado
        sb = ctk.CTkFrame(self, fg_color=MANTLE, corner_radius=0, height=32)
        sb.grid(row=1, column=1, sticky="ew")
        sb.grid_propagate(False)

        self._status_lbl = ctk.CTkLabel(
            sb, text="● Sistema listo",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=OVERLAY0, anchor="w",
        )
        self._status_lbl.pack(side="left", padx=12)

        try:
            from config import VERSION
            ver = f"v{VERSION}"
        except Exception:
            ver = "v2.0"
        ctk.CTkLabel(sb, text=ver, font=ctk.CTkFont(size=10),
                     text_color=OVERLAY0).pack(side="right", padx=12)

    def _build_sidebar(self):
        sb = self._sidebar

        # Logo
        lf = ctk.CTkFrame(sb, fg_color="transparent")
        lf.pack(fill="x", padx=16, pady=(22, 6))
        ctk.CTkLabel(lf, text="VOITHOS",
                     font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                     text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(lf, text="Auditor Contable SRI",
                     font=ctk.CTkFont(size=11), text_color=OVERLAY0,
                     anchor="w").pack(anchor="w")

        ctk.CTkFrame(sb, height=1, fg_color=SURFACE0).pack(fill="x", padx=12, pady=(12, 6))

        # Herramientas
        ctk.CTkLabel(sb, text="HERRAMIENTAS", font=ctk.CTkFont(size=10),
                     text_color=OVERLAY0, anchor="w").pack(anchor="w", padx=18, pady=(2, 4))

        for vista, label, icono in [
            ("dashboard",   "Inicio",             "⌂  "),
            ("auditoria",   "Auditoría Mensual",   "◈  "),
            ("compras",     "Revisar Compras",     "◉  "),
            ("retenciones", "Revisar Retenciones", "◎  "),
            ("pdfs",        "Organizar PDFs",      "▣  "),
        ]:
            btn = ctk.CTkButton(
                sb, text=f"{icono}{label}", anchor="w",
                fg_color="transparent", hover_color=SURFACE0,
                text_color=SUBTEXT0, font=ctk.CTkFont(size=13),
                height=36, corner_radius=6,
                command=lambda v=vista: self._navigate(v),
            )
            btn.pack(fill="x", padx=8, pady=1)
            self._nav_btns[vista] = btn

        ctk.CTkFrame(sb, height=1, fg_color=SURFACE0).pack(fill="x", padx=12, pady=(8, 6))

        # Sesión
        ctk.CTkLabel(sb, text="SESIÓN", font=ctk.CTkFont(size=10),
                     text_color=OVERLAY0, anchor="w").pack(anchor="w", padx=18, pady=(2, 4))

        btn_h = ctk.CTkButton(
            sb, text="⏱  Historial", anchor="w",
            fg_color="transparent", hover_color=SURFACE0,
            text_color=SUBTEXT0, font=ctk.CTkFont(size=13),
            height=36, corner_radius=6,
            command=lambda: self._navigate("historial"),
        )
        btn_h.pack(fill="x", padx=8, pady=1)
        self._nav_btns["historial"] = btn_h

        # Spacer + footer
        ctk.CTkFrame(sb, fg_color="transparent").pack(fill="both", expand=True)
        ctk.CTkFrame(sb, height=1, fg_color=SURFACE0).pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(sb, text="SRI · Ecuador", font=ctk.CTkFont(size=10),
                     text_color=OVERLAY0).pack(pady=(0, 14))

    # ── Navegación ─────────────────────────────────────────────────────────────

    def _navigate(self, vista: str):
        for w in self._content.winfo_children():
            w.destroy()
        self._update_nav(vista)
        {
            "dashboard":   self._show_dashboard,
            "auditoria":   self._show_panel_auditoria,
            "compras":     self._show_panel_compras,
            "retenciones": self._show_panel_retenciones,
            "pdfs":        self._show_panel_pdfs,
            "historial":   self._show_historial,
        }.get(vista, self._show_dashboard)()

    def _update_nav(self, activa: str):
        for vista, btn in self._nav_btns.items():
            if vista == activa:
                btn.configure(fg_color=SURFACE0, text_color=TEXT)
            else:
                btn.configure(fg_color="transparent", text_color=SUBTEXT0)

    # ══════════════════════════════════════════════════════════════════════════
    #  VISTA: DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════

    def _show_dashboard(self):
        sf = self._scrollable()

        hora    = datetime.now().hour
        saludo  = ("Buenos días" if hora < 12 else
                   "Buenas tardes" if hora < 19 else "Buenas noches")

        ctk.CTkLabel(sf,
                     text=f"{saludo} — ¿Qué necesitas hacer hoy?",
                     font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
                     text_color=TEXT, anchor="w",
                     ).pack(anchor="w", padx=28, pady=(24, 2))

        ctk.CTkLabel(sf, text="Selecciona una herramienta para comenzar.",
                     font=ctk.CTkFont(size=13), text_color=SUBTEXT0,
                     anchor="w").pack(anchor="w", padx=28, pady=(0, 20))

        grid = ctk.CTkFrame(sf, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=(0, 28))
        grid.columnconfigure((0, 1), weight=1, uniform="col")

        for idx, data in enumerate([
            {
                "vista": "auditoria", "icono": "📊", "color": BLUE,
                "titulo": "Auditoría Mensual",
                "desc": "Compara todos tus comprobantes del mes y detecta diferencias "
                        "entre el SRI y tu sistema contable.",
                "req": "ZIP facturas · ZIP retenciones · TXT del SRI · Sistema contable",
                "btn_text": "Comenzar auditoría →",
            },
            {
                "vista": "compras", "icono": "🧾", "color": GREEN,
                "titulo": "Revisar Compras",
                "desc": "¿Están todas tus facturas de compra registradas en el sistema? "
                        "Encuentra las que faltan o no coinciden.",
                "req": "ZIP facturas · TXT del SRI · Sistema contable",
                "btn_text": "Revisar compras →",
            },
            {
                "vista": "retenciones", "icono": "📋", "color": MAUVE,
                "titulo": "Revisar Retenciones",
                "desc": "Verifica que cada retención de tus clientes tenga su XML "
                        "y esté correctamente registrada.",
                "req": "ZIP retenciones · Ventas Personalizado",
                "btn_text": "Revisar retenciones →",
            },
            {
                "vista": "pdfs", "icono": "📁", "color": PEACH,
                "titulo": "Organizar PDFs",
                "desc": "Renombra y organiza los PDFs de comprobantes usando el número "
                        "oficial del comprobante electrónico.",
                "req": "ZIP con XMLs + PDFs juntos",
                "btn_text": "Organizar PDFs →",
            },
        ]):
            self._dashboard_card(grid, data, row=idx // 2, col=idx % 2)

        self._set_status("● Sistema listo")

    def _dashboard_card(self, parent, data: dict, row: int, col: int):
        card = ctk.CTkFrame(parent, fg_color=SURFACE0, corner_radius=12, border_width=0)
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(sticky="nsew", padx=18, pady=18)
        inner.columnconfigure(0, weight=1)

        ctk.CTkLabel(inner, text=data["icono"],
                     font=ctk.CTkFont(size=34), anchor="w",
                     ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        ctk.CTkLabel(inner, text=data["titulo"],
                     font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                     text_color=TEXT, anchor="w",
                     ).grid(row=1, column=0, sticky="w")

        ctk.CTkLabel(inner, text=data["desc"],
                     font=ctk.CTkFont(size=12), text_color=SUBTEXT0,
                     anchor="w", wraplength=270, justify="left",
                     ).grid(row=2, column=0, sticky="w", pady=(6, 10))

        ctk.CTkFrame(inner, height=1, fg_color=SURFACE1,
                     ).grid(row=3, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(inner, text=data["req"],
                     font=ctk.CTkFont(size=10), text_color=OVERLAY0,
                     anchor="w", wraplength=270, justify="left",
                     ).grid(row=4, column=0, sticky="w", pady=(0, 10))

        ctk.CTkButton(
            inner, text=data["btn_text"], font=ctk.CTkFont(size=12),
            fg_color="transparent", border_width=1,
            border_color=data["color"], text_color=data["color"],
            hover_color=SURFACE1, height=34, corner_radius=6,
            command=lambda v=data["vista"]: self._navigate(v),
        ).grid(row=5, column=0, sticky="ew")

        # Badge: última ejecución
        for h in reversed(self._historial):
            if h["tipo"] == data["vista"]:
                sc  = h.get("stats_c", {})
                sr  = h.get("stats_r", {})
                dif = (sc.get("no_en_sistema", 0) + sc.get("solo_en_sistema", 0) +
                       sr.get("sin_sistema", 0)   + sr.get("sin_xml", 0))
                ctk.CTkLabel(inner,
                             text=f"Última: {h['ts']}",
                             font=ctk.CTkFont(size=10),
                             text_color=RED if dif > 0 else TEAL,
                             anchor="w",
                             ).grid(row=6, column=0, sticky="w", pady=(8, 0))
                break

        # Hover: borde del color del acento
        def _on_enter(e): card.configure(border_width=1, border_color=data["color"])
        def _on_leave(e): card.configure(border_width=0)
        card.bind("<Enter>", _on_enter)
        card.bind("<Leave>", _on_leave)

    # ══════════════════════════════════════════════════════════════════════════
    #  VISTA: PANEL AUDITORÍA MENSUAL
    # ══════════════════════════════════════════════════════════════════════════

    def _show_panel_auditoria(self):
        sf      = self._scrollable()
        entries = {}

        self._panel_header(sf,
                           "📊  Auditoría Mensual Completa",
                           "Compara todos los comprobantes del mes y genera un reporte Excel "
                           "con las diferencias entre el SRI y tu sistema contable.",
                           BLUE)

        # PASO 1 — Drop zone
        self._section_lbl(sf, "PASO 1 — CARPETA DEL MES")
        drop = self._drop_zone(sf, height=90,
                               text="📂  Arrastra aquí la carpeta del mes\n"
                                    "(o usa los campos de abajo)")
        drop.pack(fill="x", padx=24, pady=(0, 16))
        self._reg_drop(drop, lambda paths: paths and self._autodetect(paths[0], entries))

        # PASO 2 — Archivos detectados
        self._section_lbl(sf, "PASO 2 — ARCHIVOS DETECTADOS")
        ff = ctk.CTkFrame(sf, fg_color=SURFACE0, corner_radius=10)
        ff.pack(fill="x", padx=24, pady=(0, 16))
        ff.columnconfigure(1, weight=1)

        for i, (key, lbl, tipo, hint, color, opc) in enumerate([
            ("facturas",    "📦  ZIP de Facturas de Compra",     "zip",     "ZIP con XML + PDF de facturas",            BLUE,   False),
            ("retenciones", "📦  ZIP de Retenciones Recibidas",  "zip",     "ZIP con XML + PDF de retenciones",         BLUE,   False),
            ("sistema",     "📊  Sistema Contable",              "archivo", "ReporteComprasVentas.xlsx",                BLUE,   False),
            ("sri_txt",     "📄  TXT del SRI",                   "carpeta", "Archivo o carpeta — comprobantes recibidos", BLUE,  False),
            ("ventas_pers", "📋  Ventas Personalizado",          "archivo", "Opcional — ventas con retenciones",        YELLOW, True),
        ]):
            entries[key] = self._file_row(ff, lbl, hint, i, tipo, color,
                                          saved=self._saved["auditoria"].get(key, ""),
                                          opcional=opc)

        # PASO 3 — Ejecutar
        self._section_lbl(sf, "PASO 3 — EJECUTAR")
        bf = ctk.CTkFrame(sf, fg_color="transparent")
        bf.pack(fill="x", padx=24, pady=(0, 28))
        bf.columnconfigure(0, weight=1)

        btn = ctk.CTkButton(
            bf, text="📊  Generar Auditoría Completa",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=BLUE, hover_color="#6ba3f0", text_color=BASE,
            height=46, corner_radius=8,
        )
        btn.configure(command=lambda: self._start_analysis("auditoria", entries, btn))
        btn.grid(row=0, column=0, sticky="ew")

        var_pdfs = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(bf, text="  También organizar PDFs al ejecutar",
                        variable=var_pdfs, font=ctk.CTkFont(size=12),
                        text_color=SUBTEXT0, fg_color=BLUE,
                        hover_color=SURFACE1, checkmark_color=BASE,
                        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        entries["_var_pdfs"] = var_pdfs

        self._set_status("● Arrastra la carpeta del mes para auto-detectar los archivos")

    # ══════════════════════════════════════════════════════════════════════════
    #  VISTA: PANEL COMPRAS
    # ══════════════════════════════════════════════════════════════════════════

    def _show_panel_compras(self):
        sf      = self._scrollable()
        entries = {}

        self._panel_header(sf,
                           "🧾  Revisar Compras del Mes",
                           "¿Están todas tus facturas de compra registradas en el sistema? "
                           "Compara el SRI contra tu sistema y encuentra las que faltan.",
                           GREEN)

        self._section_lbl(sf, "ARCHIVOS NECESARIOS")
        ff = ctk.CTkFrame(sf, fg_color=SURFACE0, corner_radius=10)
        ff.pack(fill="x", padx=24, pady=(0, 12))
        ff.columnconfigure(1, weight=1)

        for i, (key, lbl, tipo, hint, opc) in enumerate([
            ("facturas", "📦  ZIP de Facturas de Compra",   "zip",     "ZIP con XML + PDF del SRI",           False),
            ("sri_txt",  "📄  TXT del SRI",                 "carpeta", "Comprobantes recibidos exportados",   False),
            ("sistema",  "📊  Sistema Contable",             "archivo", "ReporteComprasVentas.xlsx",           False),
        ]):
            entries[key] = self._file_row(ff, lbl, hint, i, tipo, GREEN,
                                          saved=self._saved["compras"].get(key, ""),
                                          opcional=opc)

        drop = self._drop_zone(sf, height=60,
                               text="📂  Arrastra la carpeta del mes para auto-detectar")
        drop.pack(fill="x", padx=24, pady=(8, 16))
        self._reg_drop(drop, lambda paths: paths and self._autodetect(paths[0], entries))

        btn = ctk.CTkButton(sf, text="🧾  Revisar Compras",
                            font=ctk.CTkFont(size=14, weight="bold"),
                            fg_color=GREEN, hover_color="#8fcf8d", text_color=BASE,
                            height=44, corner_radius=8)
        btn.configure(command=lambda: self._start_analysis("compras", entries, btn))
        btn.pack(fill="x", padx=24, pady=(0, 28))

        self._set_status("● Configura los archivos para revisar compras del mes")

    # ══════════════════════════════════════════════════════════════════════════
    #  VISTA: PANEL RETENCIONES
    # ══════════════════════════════════════════════════════════════════════════

    def _show_panel_retenciones(self):
        sf      = self._scrollable()
        entries = {}

        self._panel_header(sf,
                           "📋  Revisar Retenciones",
                           "Verifica que cada retención de tus clientes tenga su XML "
                           "y esté correctamente registrada en el sistema.",
                           MAUVE)

        self._section_lbl(sf, "ARCHIVOS NECESARIOS")
        ff = ctk.CTkFrame(sf, fg_color=SURFACE0, corner_radius=10)
        ff.pack(fill="x", padx=24, pady=(0, 12))
        ff.columnconfigure(1, weight=1)

        for i, (key, lbl, tipo, hint, opc) in enumerate([
            ("retenciones", "📦  ZIP de Retenciones Recibidas",  "zip",     "ZIP con XML + PDF del SRI",               False),
            ("ventas_pers", "📋  Ventas Personalizado",          "archivo", "Excel con ventas que tienen retenciones",  False),
        ]):
            entries[key] = self._file_row(ff, lbl, hint, i, tipo, MAUVE,
                                          saved=self._saved["retenciones"].get(key, ""),
                                          opcional=opc)

        drop = self._drop_zone(sf, height=60,
                               text="📂  Arrastra la carpeta del mes para auto-detectar")
        drop.pack(fill="x", padx=24, pady=(8, 16))
        self._reg_drop(drop, lambda paths: paths and self._autodetect(paths[0], entries))

        btn = ctk.CTkButton(sf, text="📋  Revisar Retenciones",
                            font=ctk.CTkFont(size=14, weight="bold"),
                            fg_color=MAUVE, hover_color="#b892f5", text_color=BASE,
                            height=44, corner_radius=8)
        btn.configure(command=lambda: self._start_analysis("retenciones", entries, btn))
        btn.pack(fill="x", padx=24, pady=(0, 28))

        self._set_status("● Configura los archivos para revisar retenciones")

    # ══════════════════════════════════════════════════════════════════════════
    #  VISTA: PANEL ORGANIZAR PDFs
    # ══════════════════════════════════════════════════════════════════════════

    def _show_panel_pdfs(self):
        sf      = self._scrollable()
        entries = {}

        self._panel_header(sf,
                           "📁  Organizar PDFs de Comprobantes",
                           "Renombra y organiza los PDFs usando el número oficial del comprobante. "
                           "Los archivos originales no se modifican — se crean copias en processed_data/.",
                           PEACH)

        # Nota informativa
        nota = ctk.CTkFrame(sf, fg_color=MANTLE, corner_radius=8)
        nota.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkLabel(
            nota,
            text="ℹ️  Comprime en un ZIP la carpeta con los XML + PDF del SRI.\n"
                 "     Ejemplo:  Factura(1).xml  +  Factura(1).pdf  →  ZIP  →  001-001-000005254.pdf\n"
                 "     El programa genera un ZIP con los PDFs renombrados en processed_data/.",
            font=ctk.CTkFont(size=12), text_color=SUBTEXT0,
            justify="left", anchor="w",
        ).pack(padx=14, pady=12, anchor="w")

        self._section_lbl(sf, "CARPETAS DE COMPROBANTES")
        ff = ctk.CTkFrame(sf, fg_color=SURFACE0, corner_radius=10)
        ff.pack(fill="x", padx=24, pady=(0, 12))
        ff.columnconfigure(1, weight=1)

        for i, (key, lbl, hint, opc) in enumerate([
            ("facturas",    "📦  ZIP de Facturas de Compra",    "ZIP con XMLs + PDFs de facturas",    False),
            ("retenciones", "📦  ZIP de Retenciones Recibidas", "ZIP con XMLs + PDFs de retenciones", True),
        ]):
            entries[key] = self._file_row(ff, lbl, hint, i, "zip", PEACH,
                                          saved=self._saved["pdfs"].get(key, ""),
                                          opcional=opc)

        drop = self._drop_zone(sf, height=60,
                               text="📂  Arrastra la carpeta del mes para auto-detectar")
        drop.pack(fill="x", padx=24, pady=(8, 16))
        self._reg_drop(drop, lambda paths: paths and self._autodetect(paths[0], entries))

        btn = ctk.CTkButton(sf, text="📁  Organizar PDFs",
                            font=ctk.CTkFont(size=14, weight="bold"),
                            fg_color=PEACH, hover_color="#f0a07c", text_color=BASE,
                            height=44, corner_radius=8)
        btn.configure(command=lambda: self._start_analysis("pdfs", entries, btn))
        btn.pack(fill="x", padx=24, pady=(0, 28))

        self._set_status("● Los XMLs y sus PDFs deben estar en la misma carpeta")

    # ══════════════════════════════════════════════════════════════════════════
    #  VISTA: HISTORIAL
    # ══════════════════════════════════════════════════════════════════════════

    def _show_historial(self):
        sf = self._scrollable()
        self._panel_header(sf, "⏱  Historial de Auditorías",
                           "Auditorías realizadas en esta sesión.", BLUE, back_vista=None)

        if not self._historial:
            empty = ctk.CTkFrame(sf, fg_color=SURFACE0, corner_radius=10)
            empty.pack(fill="x", padx=24, pady=16)
            ctk.CTkLabel(empty,
                         text="Aún no hay auditorías en esta sesión.\n"
                              "Ejecuta una auditoría para ver los resultados aquí.",
                         font=ctk.CTkFont(size=13), text_color=OVERLAY0,
                         justify="center").pack(pady=28)
            return

        for entry in reversed(self._historial):
            self._history_card(sf, entry)

    def _history_card(self, parent, entry: dict):
        meta = {
            "auditoria":   ("📊", "Auditoría Completa",   BLUE),
            "compras":     ("🧾", "Revisión de Compras",   GREEN),
            "retenciones": ("📋", "Revisión Retenciones",  MAUVE),
            "pdfs":        ("📁", "Organización de PDFs",  PEACH),
        }
        icono, tipo_str, color = meta.get(entry["tipo"], ("📊", "Análisis", BLUE))

        card = ctk.CTkFrame(parent, fg_color=SURFACE0, corner_radius=10)
        card.pack(fill="x", padx=24, pady=(0, 8))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 4))
        top.columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text=f"{icono}  {tipo_str}",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=color, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(top, text=entry["ts"],
                     font=ctk.CTkFont(size=11), text_color=OVERLAY0,
                     anchor="e").grid(row=0, column=1, sticky="e")

        sc  = entry.get("stats_c", {})
        sr  = entry.get("stats_r", {})
        dif = (sc.get("no_en_sistema", 0) + sc.get("solo_en_sistema", 0) +
               sr.get("sin_sistema",   0) + sr.get("sin_xml",         0))

        ctk.CTkLabel(card,
                     text=f"🔴 {dif} diferencias encontradas" if dif > 0
                     else "✅ Sin diferencias — todo en orden",
                     font=ctk.CTkFont(size=11),
                     text_color=RED if dif > 0 else TEAL,
                     anchor="w").pack(anchor="w", padx=14, pady=(0, 4))

        if entry.get("path") and os.path.exists(entry["path"]):
            ctk.CTkButton(card, text="Ver reporte →",
                          font=ctk.CTkFont(size=11),
                          fg_color="transparent", text_color=color,
                          hover_color=SURFACE1, height=28, anchor="w",
                          command=lambda p=entry["path"]: self._abrir(p),
                          ).pack(anchor="w", padx=10, pady=(0, 10))
        else:
            ctk.CTkFrame(card, height=8, fg_color="transparent").pack()

    # ══════════════════════════════════════════════════════════════════════════
    #  VISTA: RESULTADOS
    # ══════════════════════════════════════════════════════════════════════════

    def _show_resultados(self, tipo: str, stats_c: dict, stats_r: dict,
                         out_path: str, log_text: str, analysis_id: int):
        # Ignorar si el usuario ya navegó a otra pantalla
        if analysis_id != self._analysis_id:
            return

        for w in self._content.winfo_children():
            w.destroy()
        sf = self._scrollable()

        # ── Banner de estado ──────────────────────────────────────────────────
        dif = (stats_c.get("no_en_sistema", 0) + stats_c.get("solo_en_sistema", 0) +
               stats_r.get("sin_sistema",   0) + stats_r.get("sin_xml",         0))

        banner = ctk.CTkFrame(sf, fg_color=MANTLE, corner_radius=10)
        banner.pack(fill="x", padx=24, pady=(20, 16))

        if dif == 0:
            est_txt, est_color = "✅  Sin diferencias encontradas", TEAL
            est_desc = "Todo está en orden. Los comprobantes coinciden en todas las fuentes."
        else:
            est_txt, est_color = f"⚠️  Se encontraron {dif} diferencias", YELLOW
            est_desc = "Revisa las hojas en rojo y naranja del reporte Excel generado."

        ctk.CTkLabel(banner, text=est_txt,
                     font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                     text_color=est_color, anchor="w").pack(anchor="w", padx=18, pady=(14, 4))
        ctk.CTkLabel(banner, text=est_desc,
                     font=ctk.CTkFont(size=12), text_color=SUBTEXT0,
                     anchor="w").pack(anchor="w", padx=18, pady=(0, 14))

        # ── Tarjetas de métricas ──────────────────────────────────────────────
        metricas = []
        if tipo in ("auditoria", "compras"):
            no_sis = stats_c.get("no_en_sistema",  0)
            solo   = stats_c.get("solo_en_sistema", 0)
            ok_c   = stats_c.get("en_todos",        0)
            metricas += [
                (str(no_sis), "En SRI\nsin Sistema",     RED    if no_sis > 0 else TEAL),
                (str(solo),   "Solo Sistema\nsin SRI",   YELLOW if solo   > 0 else TEAL),
                (str(ok_c),   "Coinciden\ncorrectamente",TEAL),
            ]
        if tipo in ("auditoria", "retenciones"):
            dif_r = stats_r.get("sin_sistema", 0) + stats_r.get("sin_xml", 0)
            metricas.append(
                (str(dif_r), "Retenciones\ncon diferencias", RED if dif_r > 0 else TEAL))

        if metricas:
            mf = ctk.CTkFrame(sf, fg_color="transparent")
            mf.pack(fill="x", padx=24, pady=(0, 16))
            for i in range(len(metricas)):
                mf.columnconfigure(i, weight=1, uniform="mc")
            for col_i, (valor, etiqueta, color) in enumerate(metricas):
                mc = ctk.CTkFrame(mf, fg_color=SURFACE0, corner_radius=10)
                mc.grid(row=0, column=col_i, padx=4, sticky="ew")
                ctk.CTkLabel(mc, text=valor,
                             font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
                             text_color=color).pack(pady=(16, 4))
                ctk.CTkLabel(mc, text=etiqueta,
                             font=ctk.CTkFont(size=11), text_color=SUBTEXT0,
                             justify="center").pack(pady=(0, 14))

        # ── PDFs organizados (modo pdfs) ──────────────────────────────────────
        if tipo == "pdfs":
            info = ctk.CTkFrame(sf, fg_color=SURFACE0, corner_radius=10)
            info.pack(fill="x", padx=24, pady=(0, 16))
            if out_path and os.path.exists(out_path):
                zip_name = os.path.basename(out_path)
                zip_dir  = os.path.dirname(out_path)
                texto_pdf = (f"✅  PDFs renombrados y empaquetados en ZIP\n"
                             f"    {zip_name}")
            else:
                zip_dir   = ""
                texto_pdf = "ℹ️  No se encontraron PDFs para empaquetar"
            ctk.CTkLabel(info, text=texto_pdf,
                         font=ctk.CTkFont(size=13), text_color=TEAL,
                         justify="left", anchor="w").pack(padx=18, pady=(18, 4), anchor="w")
            if zip_dir:
                ctk.CTkLabel(info, text=f"    📁  {zip_dir}",
                             font=ctk.CTkFont(size=11), text_color=SUBTEXT0,
                             anchor="w").pack(padx=18, pady=(0, 14), anchor="w")

        # ── Log de ejecución ──────────────────────────────────────────────────
        log_f = ctk.CTkFrame(sf, fg_color=SURFACE0, corner_radius=10)
        log_f.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkLabel(log_f, text="Registro de ejecución",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=SUBTEXT0, anchor="w").pack(anchor="w", padx=14, pady=(10, 4))
        log_box = ctk.CTkTextbox(log_f,
                                 font=ctk.CTkFont(family="Courier New", size=11),
                                 fg_color=MANTLE, text_color=SUBTEXT0,
                                 border_width=0, height=150,
                                 state="normal", wrap="none")
        log_box.pack(fill="x", padx=10, pady=(0, 10))
        log_box.insert("1.0", log_text or "(sin salida registrada)")
        log_box.configure(state="disabled")

        # ── Botones de acción ─────────────────────────────────────────────────
        bf = ctk.CTkFrame(sf, fg_color="transparent")
        bf.pack(fill="x", padx=24, pady=(0, 28))
        bf.columnconfigure(0, weight=2)
        bf.columnconfigure(1, weight=1)

        if out_path and os.path.exists(out_path):
            btn_lbl = "📦  Abrir ZIP de PDFs" if tipo == "pdfs" else "📂  Abrir Reporte Excel"
            ctk.CTkButton(
                bf, text=btn_lbl,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=TEAL, hover_color="#7dcfba", text_color=BASE,
                height=44, corner_radius=8,
                command=lambda: self._abrir(out_path),
            ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        dest = tipo if tipo in ("auditoria", "compras", "retenciones", "pdfs") else "dashboard"
        ctk.CTkButton(
            bf, text="🔄  Nueva Auditoría",
            font=ctk.CTkFont(size=13),
            fg_color="transparent", border_width=1,
            border_color=SURFACE1, text_color=SUBTEXT0,
            hover_color=SURFACE0, height=44, corner_radius=8,
            command=lambda: self._navigate(dest),
        ).grid(row=0, column=1, sticky="ew")

    # ══════════════════════════════════════════════════════════════════════════
    #  COMPONENTES REUTILIZABLES
    # ══════════════════════════════════════════════════════════════════════════

    def _scrollable(self) -> ctk.CTkScrollableFrame:
        sf = ctk.CTkScrollableFrame(
            self._content, fg_color=BASE,
            scrollbar_button_color=SURFACE1,
            scrollbar_button_hover_color=SURFACE2,
        )
        sf.grid(row=0, column=0, sticky="nsew")
        sf.columnconfigure(0, weight=1)
        return sf

    def _panel_header(self, parent, titulo: str, desc: str,
                      color: str, back_vista: str = "dashboard"):
        ctk.CTkFrame(parent, height=3, fg_color=color, corner_radius=0).pack(fill="x")
        hdr = ctk.CTkFrame(parent, fg_color=MANTLE, corner_radius=0)
        hdr.pack(fill="x")
        inner = ctk.CTkFrame(hdr, fg_color="transparent")
        inner.pack(fill="x", padx=24, pady=(16, 18))
        inner.columnconfigure(0, weight=1)

        if back_vista:
            ctk.CTkButton(inner, text="← Inicio",
                          font=ctk.CTkFont(size=12),
                          fg_color="transparent", text_color=color,
                          hover_color=SURFACE0, height=24, width=80, anchor="w",
                          command=lambda: self._navigate(back_vista),
                          ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        ctk.CTkLabel(inner, text=titulo,
                     font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
                     text_color=TEXT, anchor="w").grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(inner, text=desc,
                     font=ctk.CTkFont(size=13), text_color=SUBTEXT0,
                     anchor="w", wraplength=700, justify="left",
                     ).grid(row=2, column=0, sticky="w", pady=(4, 0))

    def _section_lbl(self, parent, text: str):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=10),
                     text_color=OVERLAY0, anchor="w",
                     ).pack(anchor="w", padx=28, pady=(16, 4))

    def _file_row(self, parent, label: str, hint: str, row: int,
                  tipo: str, color: str, saved: str = "",
                  opcional: bool = False) -> ctk.CTkEntry:
        """Una fila de selección de archivo/carpeta dentro de un frame con grid."""
        # Etiqueta (columna 0)
        lf = ctk.CTkFrame(parent, fg_color="transparent")
        lf.grid(row=row, column=0, sticky="w", padx=(14, 4), pady=8)
        ctk.CTkLabel(lf, text=label,
                     font=ctk.CTkFont(size=12),
                     text_color=TEXT if not opcional else SUBTEXT0,
                     anchor="w").pack(side="left")
        if opcional:
            ctk.CTkLabel(lf, text="  opcional",
                         font=ctk.CTkFont(size=10), text_color=OVERLAY0).pack(side="left")

        # Entry + botón (columna 1)
        ef = ctk.CTkFrame(parent, fg_color="transparent")
        ef.grid(row=row, column=1, sticky="ew", padx=(0, 14), pady=8)
        ef.columnconfigure(0, weight=1)

        entry = ctk.CTkEntry(ef, placeholder_text=hint,
                             fg_color=MANTLE, border_color=SURFACE1,
                             text_color=TEXT, placeholder_text_color=OVERLAY0,
                             height=32, font=ctk.CTkFont(size=12))
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        if saved:
            entry.insert(0, saved)

        # Drag & drop directo sobre el campo
        def _make_drop_handler(e, t=tipo):
            paths = self._parse_paths(e.data)
            if not paths:
                return
            p = paths[0]
            # Validar según tipo esperado
            if t == "zip" and p.lower().endswith('.zip') and os.path.isfile(p):
                pass  # ok
            elif t == "carpeta" and (os.path.isdir(p) or p.lower().endswith('.txt')):
                pass  # ok — carpeta o archivo TXT individual
            elif t == "archivo" and os.path.isfile(p):
                pass  # ok — cualquier archivo (.xlsx, .txt, etc.)
            else:
                self._set_status(f"⚠️  Tipo de archivo incorrecto para este campo", YELLOW)
                return
            entry.delete(0, "end")
            entry.insert(0, p)
            entry.configure(border_color=TEAL)
            self.after(1500, lambda: entry.configure(border_color=SURFACE1))

        try:
            entry.drop_target_register(DND_FILES)
            entry.dnd_bind("<<Drop>>", _make_drop_handler)
        except Exception:
            pass  # tkinterdnd2 no disponible en este widget — ignorar silenciosamente

        ctk.CTkButton(ef, text="...", width=36, height=32,
                      fg_color=SURFACE1, hover_color=SURFACE2,
                      text_color=TEXT, font=ctk.CTkFont(size=12), corner_radius=6,
                      command=lambda t=tipo: self._browse(entry, t),
                      ).grid(row=0, column=1)
        return entry

    def _drop_zone(self, parent, height: int = 90, text: str = "Arrastra aquí") -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, height=height,
                             fg_color=MANTLE, border_color=SURFACE1,
                             border_width=2, corner_radius=10)
        lbl = ctk.CTkLabel(frame, text=text,
                            font=ctk.CTkFont(size=12), text_color=OVERLAY0)
        lbl.place(relx=0.5, rely=0.5, anchor="center")
        frame._lbl = lbl
        return frame

    def _reg_drop(self, frame: ctk.CTkFrame, callback):
        """Registra drag & drop en un frame de zona drop."""
        lbl = getattr(frame, "_lbl", None)

        def _enter(e):
            frame.configure(border_color=BLUE)
            if lbl:
                lbl.configure(text_color=BLUE)

        def _leave(e):
            frame.configure(border_color=SURFACE1)
            if lbl:
                lbl.configure(text_color=OVERLAY0)

        def _drop(e):
            paths = self._parse_paths(e.data)
            frame.configure(border_color=SURFACE1)
            if lbl:
                lbl.configure(text_color=OVERLAY0)
            if paths:
                p = paths[0]
                if os.path.isdir(p):
                    callback([p])
                elif os.path.isfile(p) and p.lower().endswith('.zip'):
                    callback([p])
                else:
                    self._set_status(
                        f"⚠️  Arrastra una CARPETA o un archivo .zip: {os.path.basename(p)}", YELLOW)

        for w in ([frame] + ([lbl] if lbl else [])):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<DragEnter>>", _enter)
            w.dnd_bind("<<DragLeave>>", _leave)
            w.dnd_bind("<<Drop>>",      _drop)

    def _parse_paths(self, data: str) -> list:
        """Parsea la cadena de rutas de TkinterDnD2 (maneja rutas con espacios)."""
        return [(m.group(1) or m.group(2)).strip()
                for m in re.finditer(r'\{([^}]+)\}|(\S+)', data)]

    def _autodetect(self, base: str, entries: dict):
        """Auto-detecta archivos en base y rellena los CTkEntry del panel activo."""
        if not base:
            return
        # Si es un ZIP: rellenar directamente el campo facturas o retenciones según el nombre
        if os.path.isfile(base) and base.lower().endswith('.zip'):
            nombre = os.path.basename(base).lower()
            if any(k in nombre for k in ('factura', 'compra')):
                key = 'facturas'
            elif any(k in nombre for k in ('retencion', 'retention')):
                key = 'retenciones'
            else:
                key = 'facturas'   # asumir facturas si no se puede determinar
            e = entries.get(key)
            if isinstance(e, ctk.CTkEntry):
                e.delete(0, "end")
                e.insert(0, base)
                self._set_status(f"✅  ZIP asignado a {key}: {os.path.basename(base)}", TEAL)
            return
        # Si no es carpeta tampoco
        if not os.path.isdir(base):
            self._set_status(
                "⚠️  Arrastra una CARPETA o un archivo .zip.", YELLOW)
            return
        try:
            from util.archivos import detectar_estructura
            det = detectar_estructura(base)
        except ValueError as e:
            self._set_status(f"⚠️  {e}", YELLOW)
            return
        except Exception as e:
            self._set_status(f"⚠️  Error al detectar estructura: {e}", YELLOW)
            return

        mapa = {
            "facturas":    det.get("facturas"),
            "retenciones": det.get("retenciones"),
            "sistema":     det.get("sistema"),
            "ventas_pers": det.get("ventas_pers"),
            "sri_txt":     det.get("sri_txt"),
        }
        llenos = total = 0
        for key, valor in mapa.items():
            e = entries.get(key)
            if not isinstance(e, ctk.CTkEntry):
                continue
            total += 1
            if valor:
                e.delete(0, "end")
                e.insert(0, valor)
                llenos += 1

        if llenos == total and total > 0:
            self._set_status(f"✅  {llenos}/{total} archivos detectados automáticamente", TEAL)
        elif llenos > 0:
            self._set_status(
                f"⚠️  {llenos}/{total} detectados — completa los campos vacíos manualmente", YELLOW)
        else:
            self._set_status(
                "⚠️  No se detectaron archivos — completa los campos manualmente", YELLOW)

    def _browse(self, entry: ctk.CTkEntry, tipo: str):
        from tkinter import filedialog
        if tipo == "carpeta":
            # Ofrecer tanto carpeta como archivo TXT individual
            from tkinter import messagebox
            eleccion = messagebox.askquestion(
                "TXT del SRI",
                "¿Quieres seleccionar una CARPETA con TXT(s) del SRI?\n\n"
                "Sí → seleccionar carpeta\nNo → seleccionar archivo .txt individual",
                icon="question",
            )
            if eleccion == "yes":
                p = filedialog.askdirectory(title="Seleccionar carpeta con TXT del SRI")
            else:
                p = filedialog.askopenfilename(
                    title="Seleccionar archivo TXT del SRI",
                    filetypes=[("TXT", "*.txt"), ("Todos", "*.*")],
                )
        elif tipo == "zip":
            p = filedialog.askopenfilename(
                title="Seleccionar archivo ZIP",
                filetypes=[("ZIP", "*.zip"), ("Todos", "*.*")],
            )
        else:
            p = filedialog.askopenfilename(
                title="Seleccionar archivo",
                filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")],
            )
        if p:
            entry.delete(0, "end")
            entry.insert(0, p)

    # ══════════════════════════════════════════════════════════════════════════
    #  MOTOR DE ANÁLISIS
    # ══════════════════════════════════════════════════════════════════════════

    def _entry_val(self, entries: dict, key: str) -> str:
        e = entries.get(key)
        return e.get().strip() if isinstance(e, ctk.CTkEntry) else ""

    def _start_analysis(self, tipo: str, entries: dict, btn: ctk.CTkButton):
        rutas = {k: self._entry_val(entries, k)
                 for k in ("facturas", "retenciones", "sistema", "ventas_pers", "sri_txt")}

        # ── Validación de entradas antes de iniciar el hilo ───────────────────
        try:
            from util.validacion import validar_rutas_analisis
            errores = validar_rutas_analisis(tipo, rutas)
            if errores:
                # Mostrar el primer error en la barra de estado
                self._set_status(f"⚠️  {errores[0].splitlines()[0]}", YELLOW)
                return
        except ImportError:
            pass  # módulo no disponible, continuar sin validar

        # Persistir rutas
        if tipo in self._saved:
            self._saved[tipo] = {k: v for k, v in rutas.items() if v}

        var_pdfs       = entries.get("_var_pdfs")
        organizar_pdfs = var_pdfs.get() if var_pdfs else False

        # Nuevo ID de análisis — invalida resultados anteriores si el usuario navega
        self._analysis_id += 1
        current_id = self._analysis_id

        accion = {
            "auditoria":   "Generando auditoría...",
            "compras":     "Revisando compras...",
            "retenciones": "Revisando retenciones...",
            "pdfs":        "Organizando PDFs...",
        }.get(tipo, "Procesando...")

        btn.configure(state="disabled", text=f"⏳  {accion}")
        self._set_status(f"⏳  {accion}")

        threading.Thread(
            target=self._hilo,
            args=(tipo, rutas, btn, organizar_pdfs, current_id),
            daemon=True,
        ).start()

    def _hilo(self, tipo: str, rutas: dict, btn: ctk.CTkButton,
              organizar_pdfs: bool, analysis_id: int):
        """Hilo de trabajo: ejecuta el análisis y notifica a la UI al terminar."""
        import pandas as pd

        log_buf    = []
        old_stdout = sys.stdout
        sys.stdout = _BufferWriter(log_buf)

        stats_c  = {}
        stats_r  = {}
        out_path = ""
        temps_a_limpiar = []   # directorios temp extraídos de ZIPs

        try:
            from config import CARPETA_SALIDA
            from parsers.facturas_xml         import parsear_factura_xml
            from parsers.retenciones_xml      import parsear_retencion_xml
            from parsers.sri_txt              import cargar_txt_sri
            from loaders.sistema_excel        import cargar_sistema
            from loaders.ventas_personalizado import cargar_ventas_personalizado
            from comparadores.comparar_compras      import comparar_compras
            from comparadores.comparar_retenciones  import comparar_retenciones
            from reportes.generar_excel       import generar_reporte
            from util.archivos import (cargar_xmls_carpeta,
                                       extraer_zip_a_temp,
                                       pdfs_renombrados_a_zip)

            carpeta_sal = os.path.join(_RAIZ, CARPETA_SALIDA)
            os.makedirs(carpeta_sal, exist_ok=True)

            # Inicializar logger persistente en disco
            try:
                from util.logger import obtener_logger
                obtener_logger(carpeta_sal)
            except Exception:
                pass

            # Helper: resolver ruta (ZIP → extrae a temp, carpeta → usa directo)
            def _resolver(ruta_str: str) -> str:
                if ruta_str and ruta_str.lower().endswith('.zip') and os.path.isfile(ruta_str):
                    self._set_status(f"⏳  Extrayendo {os.path.basename(ruta_str)}...")
                    td = extraer_zip_a_temp(ruta_str)
                    temps_a_limpiar.append(td)
                    return td
                return ruta_str

            # Resolver entradas de facturas y retenciones (ZIP o carpeta)
            fac_dir = _resolver(rutas.get("facturas",    ""))
            ret_dir = _resolver(rutas.get("retenciones", ""))

            # Helper: callback de progreso granular
            def _mk_progress(label):
                def _cb(i, total):
                    self._set_status(f"⏳  {label}: {i}/{total}...")
                return _cb

            df_fac = df_ret = df_comp = df_vp = df_txt = None

            # ── PDFs renombrados → ZIP ────────────────────────────────────────
            pdfs_zip_path = ""   # ruta del ZIP de compras (para la vista de resultados)

            if tipo in ("auditoria", "pdfs") or organizar_pdfs:
                if fac_dir:
                    self._set_status("⏳  Empaquetando PDFs de facturas en ZIP...")
                    zip_bytes, c, s, e = pdfs_renombrados_a_zip(
                        fac_dir, "factura", parsear_factura_xml)
                    print(f"   Compras → Empaquetados: {c}  Sin PDF: {s}  Errores: {e}")
                    if zip_bytes:
                        pdfs_zip_path = os.path.join(
                            carpeta_sal, f"PDFs_Compras_{_ts_file()}.zip")
                        with open(pdfs_zip_path, 'wb') as f:
                            f.write(zip_bytes)
                        print(f"   ZIP guardado en: {pdfs_zip_path}")

                if ret_dir:
                    self._set_status("⏳  Empaquetando PDFs de retenciones en ZIP...")
                    zip_bytes, c, s, e = pdfs_renombrados_a_zip(
                        ret_dir, "retencion", parsear_retencion_xml)
                    print(f"   Retenciones → Empaquetados: {c}  Sin PDF: {s}  Errores: {e}")
                    if zip_bytes:
                        ret_zip_path = os.path.join(
                            carpeta_sal, f"PDFs_Retenciones_{_ts_file()}.zip")
                        with open(ret_zip_path, 'wb') as f:
                            f.write(zip_bytes)
                        print(f"   ZIP guardado en: {ret_zip_path}")
                        if not pdfs_zip_path:
                            pdfs_zip_path = ret_zip_path

            # ── Modo solo PDFs: terminar ──────────────────────────────────────
            if tipo == "pdfs":
                self._set_status("✅  PDFs organizados y empaquetados en ZIP", TEAL)
                self._historial.append({"tipo": "pdfs", "ts": _ts_label(),
                                        "stats_c": {}, "stats_r": {}, "path": pdfs_zip_path})
                lt = "".join(log_buf)
                self.after(0, lambda p=pdfs_zip_path, l=lt:
                           self._show_resultados("pdfs", {}, {}, p, l, analysis_id))
                return

            # ── Carga de datos ────────────────────────────────────────────────
            if fac_dir and tipo in ("auditoria", "compras"):
                self._set_status("⏳  Leyendo facturas XML...")
                df_fac = cargar_xmls_carpeta(
                    fac_dir, parsear_factura_xml,
                    progress_callback=_mk_progress("Facturas XML"))

            if ret_dir and tipo in ("auditoria", "retenciones"):
                self._set_status("⏳  Leyendo retenciones XML...")
                df_ret = cargar_xmls_carpeta(
                    ret_dir, parsear_retencion_xml,
                    progress_callback=_mk_progress("Retenciones XML"))

            if rutas.get("sistema") and tipo in ("auditoria", "compras"):
                self._set_status("⏳  Cargando sistema contable...")
                df_comp, _ = cargar_sistema(rutas["sistema"])

            if rutas.get("ventas_pers") and tipo in ("auditoria", "retenciones"):
                self._set_status("⏳  Cargando Ventas Personalizado...")
                df_vp = cargar_ventas_personalizado(rutas["ventas_pers"])

            if rutas.get("sri_txt") and tipo in ("auditoria", "compras"):
                self._set_status("⏳  Consultando TXT del SRI...")
                df_txt = cargar_txt_sri(rutas["sri_txt"])

            # ── Comparaciones ─────────────────────────────────────────────────
            self._set_status("⏳  Comparando compras con el sistema...")
            compras_r = comparar_compras(
                df_fac  if df_fac  is not None else pd.DataFrame(),
                df_txt  if df_txt  is not None else pd.DataFrame(),
                df_comp if df_comp is not None else pd.DataFrame(),
            )

            self._set_status("⏳  Comparando retenciones...")
            ret_r = comparar_retenciones(
                df_ret if df_ret is not None else pd.DataFrame(),
                df_vp  if df_vp  is not None else pd.DataFrame(),
            )

            # ── Generar reporte ───────────────────────────────────────────────
            self._set_status("⏳  Preparando el reporte Excel...")
            prefijo  = {"auditoria": "AUDITORIA", "compras": "COMPRAS",
                        "retenciones": "RETENCIONES"}.get(tipo, "VOITHOS")
            out_path = os.path.join(carpeta_sal, f"{prefijo}_{_ts_file()}.xlsx")
            generar_reporte(compras_r, ret_r, out_path)

            stats_c = compras_r.get("stats", {})
            stats_r = ret_r.get("stats", {})

            dif = (stats_c.get("no_en_sistema", 0) + stats_c.get("solo_en_sistema", 0) +
                   stats_r.get("sin_sistema",   0) + stats_r.get("sin_xml",         0))

            self._set_status(
                "✅  ¡Listo! Sin diferencias encontradas." if dif == 0
                else f"⚠️  ¡Listo! Se encontraron {dif} diferencias.",
                TEAL if dif == 0 else YELLOW,
            )

            self._historial.append({
                "tipo":    tipo,
                "ts":      _ts_label(),
                "stats_c": stats_c,
                "stats_r": stats_r,
                "path":    out_path,
            })

            lt = "".join(log_buf)
            self.after(0, lambda sc=stats_c, sr=stats_r, op=out_path, log=lt:
                       self._show_resultados(tipo, sc, sr, op, log, analysis_id))

        except Exception as exc:
            self._set_status(f"❌  Error: {exc}", RED)
            etiquetas = {
                "auditoria":   "📊  Generar Auditoría Completa",
                "compras":     "🧾  Revisar Compras",
                "retenciones": "📋  Revisar Retenciones",
                "pdfs":        "📁  Organizar PDFs",
            }
            self.after(0, lambda: btn.configure(
                state="normal", text=etiquetas.get(tipo, "▶  Reintentar")))

        finally:
            sys.stdout = old_stdout
            for td in temps_a_limpiar:
                shutil.rmtree(td, ignore_errors=True)

    # ══════════════════════════════════════════════════════════════════════════
    #  UTILIDADES
    # ══════════════════════════════════════════════════════════════════════════

    def _set_status(self, text: str, color: str = None):
        """Actualiza la barra de estado. Seguro desde cualquier hilo."""
        c = color or OVERLAY0
        self.after(0, lambda t=text, col=c:
                   self._status_lbl.configure(text=t, text_color=col))

    def _abrir(self, path: str):
        if not path or not os.path.exists(path):
            self._set_status(
                f"⚠️  El archivo ya no existe: {os.path.basename(path or '')}",
                YELLOW,
            )
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self._set_status(f"⚠️  No se pudo abrir el archivo: {e}", YELLOW)


# ── Auxiliares de timestamp ────────────────────────────────────────────────────

def _ts_file() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _ts_label() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


# ══════════════════════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if sys.platform == "win32" and sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    app = VoithosApp()
    app.mainloop()


if __name__ == "__main__":
    main()
