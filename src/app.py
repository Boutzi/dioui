import sys
import re
import unicodedata
import subprocess
import threading
import queue
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader, simpleSplit

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR   = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_PATH  = ASSETS_DIR / "image1.png"
CAF_PATH   = ASSETS_DIR / "image2.png"

VALID_SHEETS = ["missions_hiver", "missions_printemps", "missions_ete", "missions_automne"]
SHEET_LABELS = {
    "missions_hiver":     "Hiver",
    "missions_printemps": "Printemps",
    "missions_ete":       "Été",
    "missions_automne":   "Automne",
}

# PDF constants
PAGE_W, PAGE_H = landscape(A4)
HALF_W = PAGE_W / 2
PDF_BLUE = colors.HexColor("#1F4E79")

# ---------------------------------------------------------------------------
# Palette & fonts
# ---------------------------------------------------------------------------

BG        = "#F0F2F5"
CARD      = "#FFFFFF"
HEADER_BG = "#1F4E79"
HEADER_FG = "#FFFFFF"
ACCENT    = "#2563EB"
ACCENT_H  = "#1D4ED8"
ACCENT_D  = "#BFDBFE"
BORDER    = "#E2E8F0"
TEXT      = "#1E293B"
MUTED     = "#94A3B8"
ROW_ODD   = "#F8FAFC"
ROW_EVEN  = "#FFFFFF"
ROW_SEL   = "#DBEAFE"
LOG_BG    = "#0F172A"
LOG_FG    = "#94A3B8"
LOG_OK    = "#4ADE80"
LOG_ERR   = "#F87171"
LOG_INFO  = "#60A5FA"

F_TITLE  = ("Segoe UI", 13, "bold")
F_BODY   = ("Segoe UI", 10)
F_BOLD   = ("Segoe UI", 10, "bold")
F_SMALL  = ("Segoe UI", 9)
F_MONO   = ("Consolas", 9)

# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_]+", "-", text)

def format_date_display(raw):
    if hasattr(raw, "strftime"):
        return raw.strftime("%d/%m/%Y")
    try:
        return pd.to_datetime(str(raw), dayfirst=True).strftime("%d/%m/%Y")
    except Exception:
        return str(raw)

def format_date_slug(raw):
    if hasattr(raw, "strftime"):
        return raw.strftime("%Y-%m-%d")
    try:
        return pd.to_datetime(str(raw), dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return str(raw)

def _fit_font_size(c, text, max_w, start=8, minimum=5):
    size = start
    while size >= minimum:
        if c.stringWidth(text, "Helvetica", size) <= max_w:
            return size
        size -= 0.5
    return minimum

def _draw_wrapped(c, text, x, y_bottom, max_w, box_h, start_size=8):
    size = start_size
    while size >= 5:
        lines = simpleSplit(text, "Helvetica", size, max_w)
        if len(lines) * size * 1.3 <= box_h - 2:
            break
        size -= 0.5
    c.setFont("Helvetica", size)
    line_h = size * 1.3
    ty = y_bottom + box_h - size - 1.5
    for line in lines:
        if ty < y_bottom:
            break
        c.drawString(x, ty, line)
        ty -= line_h

def _checkbox(c, x, y, color):
    sz = 5
    c.setStrokeColor(color); c.setFillColor(colors.white); c.setLineWidth(0.5)
    c.rect(x, y - 1, sz, sz, fill=1, stroke=1)

# ---------------------------------------------------------------------------
# PDF draw
# ---------------------------------------------------------------------------

def _draw_half(c, x0, data):
    ML = x0 + 7 * mm
    MR = x0 + HALF_W - 7 * mm
    CW = MR - ML
    LABEL_W = 25 * mm
    VALUE_W = CW - LABEL_W
    y = PAGE_H - 7 * mm

    LOGO_SZ = 19 * mm
    if LOGO_PATH.exists():
        c.drawImage(ImageReader(str(LOGO_PATH)), ML, y - LOGO_SZ,
                    width=LOGO_SZ, height=LOGO_SZ,
                    preserveAspectRatio=True, mask="auto")

    title_cx = (ML + LOGO_SZ + 5 * mm + MR) / 2
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(title_cx, y - 7 * mm, "MISSION ARGENT DE POCHE")
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(title_cx, y - 14 * mm, "ATTESTATION D'INDEMNISATION")
    y -= LOGO_SZ + 4 * mm

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(ML, y, "Nom :")
    c.drawString(ML + LABEL_W + 4 * mm, y, "Prénom :")
    y -= 5 * mm

    for label, value, rh in [
        ("Date",        data["date"],        7 * mm),
        ("Heure",       data["heure"],       7 * mm),
        ("Missions",    data["description"], 18 * mm),
        ("Lieu de RDV", data["lieu_rdv"],    8 * mm),
        ("Référent",    data["referent"],    8 * mm),
        ("Contact",     data["contact"],     8 * mm),
    ]:
        c.setStrokeColor(colors.black); c.setFillColor(colors.white); c.setLineWidth(0.5)
        c.rect(ML, y - rh, LABEL_W, rh, fill=1, stroke=1)
        c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 8)
        c.drawString(ML + 1.5 * mm, y - rh / 2 - 1.5, label)

        c.setFillColor(colors.white)
        c.rect(ML + LABEL_W, y - rh, VALUE_W, rh, fill=1, stroke=1)
        c.setFillColor(colors.black)
        if label == "Missions":
            _draw_wrapped(c, value, ML + LABEL_W + 1.5 * mm,
                          y - rh, VALUE_W - 3 * mm, rh, 8)
        else:
            fs = _fit_font_size(c, value, VALUE_W - 3 * mm)
            c.setFont("Helvetica", fs)
            c.drawString(ML + LABEL_W + 1.5 * mm, y - rh / 2 - 1.5, value)
        y -= rh

    y -= 3 * mm
    c.setStrokeColor(colors.black); c.setLineWidth(0.6)
    c.line(ML, y, MR, y)
    y -= 5 * mm

    c.setFillColor(PDF_BLUE); c.setFont("Helvetica-Bold", 8)
    c.drawString(ML, y, "Fait le :          /          /")
    y -= 6 * mm

    c.drawString(ML, y, "Horaires respectés :")
    bx = ML + 43 * mm
    _checkbox(c, bx, y, PDF_BLUE); c.setFillColor(PDF_BLUE)
    c.drawString(bx + 5 * mm, y, "Oui")
    bx2 = bx + 18 * mm
    _checkbox(c, bx2, y, PDF_BLUE); c.setFillColor(PDF_BLUE)
    c.drawString(bx2 + 5 * mm, y, "Non")
    y -= 6 * mm

    c.drawString(ML, y, "Mission effectuée correctement :")
    bx = ML + 59 * mm
    _checkbox(c, bx, y, PDF_BLUE); c.setFillColor(PDF_BLUE)
    c.drawString(bx + 5 * mm, y, "Oui")
    bx2 = bx + 18 * mm
    _checkbox(c, bx2, y, PDF_BLUE); c.setFillColor(PDF_BLUE)
    c.drawString(bx2 + 5 * mm, y, "Non")
    y -= 9 * mm

    qw = CW / 2
    c.setFillColor(PDF_BLUE); c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(ML + qw / 2, y, "Signature du participant :")
    c.drawCentredString(ML + qw + qw / 2, y, "Signature de l'encadrant :")
    y -= 4 * mm
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(ML + qw / 2, y, "(Attestant du bon déroulé de la mission)")
    y -= 3 * mm

    BOX_W = qw - 8 * mm; BOX_H = 20 * mm
    c.setStrokeColor(PDF_BLUE); c.setFillColor(colors.white); c.setLineWidth(0.5)
    c.rect(ML + 2 * mm, y - BOX_H, BOX_W, BOX_H, fill=1, stroke=1)
    c.rect(ML + qw + 2 * mm, y - BOX_H, BOX_W, BOX_H, fill=1, stroke=1)
    y -= BOX_H + 3 * mm

    c.setFillColor(colors.black); c.setFont("Helvetica-Oblique", 7)
    footer = ("Pour valider votre mission et enclencher votre indemnisation, veuillez ramener "
              "cette attestation signée à l'accueil de l'Atelier du 5 bis sur les horaires d'ouverture.")
    for line in simpleSplit(footer, "Helvetica-Oblique", 7, CW):
        c.drawString(ML, y, line); y -= 4 * mm

    y -= 2 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(ML, y, "En cas de problème pendant la mission, contacter le 5 Bis :")
    y -= 5 * mm
    c.drawString(ML, y, "02.96.39.38.21 ou 06.98.11.25.80")

    if CAF_PATH.exists():
        caf_h = 18 * mm; caf_w = caf_h * (73 / 117)
        c.drawImage(ImageReader(str(CAF_PATH)), MR - caf_w, 7 * mm,
                    width=caf_w, height=caf_h,
                    preserveAspectRatio=True, mask="auto")

def generate_pdf(row, out_path):
    data = {
        "date":        format_date_display(row["date"]),
        "heure":       f"{row['h_debut']}-{row['h_fin']}",
        "description": str(row.get("description", "")),
        "lieu_rdv":    str(row.get("lieu_rdv", "")),
        "referent":    str(row.get("referent", "")),
        "contact":     str(row.get("contact", "")),
    }
    c = canvas.Canvas(str(out_path), pagesize=landscape(A4))
    _draw_half(c, 0, data)
    _draw_half(c, HALF_W, data)
    c.setStrokeColor(colors.lightgrey); c.setLineWidth(0.4); c.setDash(4, 4)
    c.line(HALF_W, 8 * mm, HALF_W, PAGE_H - 8 * mm)
    c.setDash(); c.save()

def mark_pdf_done(xlsx_path, sheet, excel_row):
    """Write TRUE to the 'pdf' column for the given Excel row (1-indexed)."""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(xlsx_path)
        ws = wb[sheet]
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        if "pdf" not in headers:
            return
        col = headers.index("pdf") + 1   # 1-indexed
        ws.cell(row=excel_row, column=col).value = True
        wb.save(xlsx_path)
    except Exception:
        pass   # non-bloquant


def generate(rows, year, sheet, xlsx_path, log_fn, progress_fn):
    out_dir = OUTPUT_DIR / year / sheet
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(rows)
    log_fn(("info", f"{total} mission(s) sélectionnée(s)\n"))
    progress_fn(0, total)
    for i, row in enumerate(rows, 1):
        date_slug  = format_date_slug(row["date"])
        heure_slug = f"{row['h_debut']}-{row['h_fin']}"
        lieu_slug  = slugify(str(row["lieu_rdv"]))
        filename   = f"{date_slug}_{heure_slug}_{lieu_slug}.pdf"
        pdf_path   = out_dir / filename
        try:
            generate_pdf(row, pdf_path)
            log_fn(("ok", f"[{i}/{total}]  {filename}\n"))
            mark_pdf_done(xlsx_path, sheet, int(row["_excel_row"]))
        except Exception as e:
            log_fn(("err", f"[{i}/{total}]  {filename} : {e}\n"))
        progress_fn(i, total)
    log_fn(("info", f"\nTerminé — {out_dir}\n"))
    return out_dir

# ---------------------------------------------------------------------------
# GUI helpers
# ---------------------------------------------------------------------------

def divider(parent, bg=BORDER, orient="h", **kw):
    if orient == "h":
        return tk.Frame(parent, bg=bg, height=1, **kw)
    return tk.Frame(parent, bg=bg, width=1, **kw)

def label(parent, text, font=F_BODY, fg=TEXT, bg=CARD, **kw):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg, **kw)

def ghost_btn(parent, text, cmd, **kw):
    return tk.Button(
        parent, text=text, command=cmd,
        bg=CARD, fg=TEXT, font=F_BODY,
        relief="solid", bd=1, padx=10, pady=5,
        highlightbackground=BORDER, highlightthickness=0,
        activebackground=BG, activeforeground=TEXT,
        cursor="hand2", **kw,
    )

def accent_btn(parent, text, cmd, **kw):
    return tk.Button(
        parent, text=text, command=cmd,
        bg=ACCENT, fg="white", font=F_BOLD,
        relief="flat", bd=0, padx=20, pady=10,
        activebackground=ACCENT_H, activeforeground="white",
        cursor="hand2", **kw,
    )

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Missions Argent de Poche")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(740, 620)

        self._xlsx_path  = tk.StringVar()
        self._sheet_var  = tk.StringVar()
        self._log_queue  = queue.Queue()
        self._out_dir    = None
        self._df         = None
        self._xlsx_str   = ""
        self._sheet_name = ""
        self._check_vars    = []
        self._check_widgets = []
        self._year          = "0000"

        self._setup_ttk()
        self._build()
        self._poll_log()

    def _setup_ttk(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TCombobox",
                    fieldbackground=CARD, background=CARD,
                    foreground=TEXT, bordercolor=BORDER,
                    selectbackground=ACCENT, selectforeground="white",
                    padding=5)
        s.configure("App.Horizontal.TProgressbar",
                    troughcolor=BORDER, background=ACCENT,
                    bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)
        s.configure("TScrollbar",
                    background=BG, troughcolor=BG,
                    bordercolor=BG, arrowcolor=MUTED,
                    gripcount=0)
        s.map("TScrollbar", background=[("active", BORDER)])

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        self._build_header()

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)   # list grows

        self._build_source(body, row=0)
        tk.Frame(body, bg=BG, height=10).grid(row=1, column=0, sticky="ew")
        self._build_list(body, row=2)
        self._build_actions(body, row=3)
        self._build_log(body, row=4)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=HEADER_BG)
        hdr.pack(fill="x")

        inner = tk.Frame(hdr, bg=HEADER_BG)
        inner.pack(fill="x", padx=20, pady=12)

        # Logo
        self._logo_img = None
        if LOGO_PATH.exists():
            try:
                raw = tk.PhotoImage(file=str(LOGO_PATH))
                # target ~48px; logo is 289px
                factor = max(1, raw.width() // 48)
                self._logo_img = raw.subsample(factor, factor)
                tk.Label(inner, image=self._logo_img,
                         bg=HEADER_BG, bd=0).pack(side="left", padx=(0, 14))
            except Exception:
                pass

        col = tk.Frame(inner, bg=HEADER_BG)
        col.pack(side="left")
        tk.Label(col, text="Missions Argent de Poche",
                 font=F_TITLE, fg=HEADER_FG, bg=HEADER_BG).pack(anchor="w")
        tk.Label(col, text="Génération d'attestations PDF",
                 font=F_SMALL, fg="#93C5FD", bg=HEADER_BG).pack(anchor="w")

    # ── Source card ───────────────────────────────────────────────────────────

    def _build_source(self, parent, row):
        card = tk.Frame(parent, bg=CARD, bd=1, relief="solid",
                        highlightbackground=BORDER, highlightthickness=0)
        card.grid(row=row, column=0, sticky="ew")
        card.columnconfigure(0, weight=1)

        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=16, pady=12)
        inner.columnconfigure(1, weight=1)

        # Row 0: file picker
        label(inner, "Fichier Excel", font=F_SMALL, fg=MUTED, bg=CARD
              ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        entry = tk.Entry(inner, textvariable=self._xlsx_path,
                         state="readonly", font=F_BODY,
                         bg="#F8FAFC", fg=TEXT, relief="solid", bd=1,
                         readonlybackground="#F8FAFC",
                         highlightbackground=BORDER)
        entry.grid(row=1, column=0, columnspan=2, sticky="ew",
                   ipady=5, padx=(0, 8))

        ghost_btn(inner, "Parcourir…", self._browse
                  ).grid(row=1, column=2, sticky="e")

        divider(inner, bg=BORDER).grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=10)

        # Row 1: period + load
        label(inner, "Période", font=F_SMALL, fg=MUTED, bg=CARD
              ).grid(row=3, column=0, sticky="w", pady=(0, 4))

        period_row = tk.Frame(inner, bg=CARD)
        period_row.grid(row=4, column=0, columnspan=3, sticky="w")

        self._combo = ttk.Combobox(
            period_row,
            textvariable=self._sheet_var,
            values=[SHEET_LABELS[s] for s in VALID_SHEETS],
            state="readonly", width=16, font=F_BODY,
        )
        self._combo.pack(side="left", padx=(0, 10))

        ghost_btn(period_row, "Charger les missions",
                  self._load_missions).pack(side="left")

    # ── Mission list ──────────────────────────────────────────────────────────

    def _build_list(self, parent, row):
        wrap = tk.Frame(parent, bg=CARD, bd=1, relief="solid",
                        highlightbackground=BORDER, highlightthickness=0)
        wrap.grid(row=row, column=0, sticky="nsew")
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(1, weight=1)

        # Toolbar
        tb = tk.Frame(wrap, bg=CARD)
        tb.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=8)

        ghost_btn(tb, "✓  Tout cocher",   self._check_all).pack(side="left", padx=(0, 6))
        ghost_btn(tb, "✕  Tout décocher", self._uncheck_all).pack(side="left", padx=(0, 16))

        tk.Frame(tb, bg=BORDER, width=1).pack(side="left", fill="y", pady=2, padx=(0, 12))

        self._sel_label = tk.Label(tb, text="—", font=F_SMALL, fg=MUTED, bg=CARD)
        self._sel_label.pack(side="left")

        divider(wrap, bg=BORDER).grid(row=1, column=0, columnspan=2, sticky="ew")

        # Scrollable canvas
        self._list_canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0)
        self._list_canvas.grid(row=2, column=0, sticky="nsew")
        wrap.rowconfigure(2, weight=1)

        vbar = ttk.Scrollbar(wrap, orient="vertical",
                              command=self._list_canvas.yview)
        vbar.grid(row=2, column=1, sticky="ns")

        hbar = ttk.Scrollbar(wrap, orient="horizontal",
                              command=self._list_canvas.xview)
        hbar.grid(row=3, column=0, columnspan=2, sticky="ew")

        self._list_canvas.configure(
            yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        self._list_frame = tk.Frame(self._list_canvas, bg=CARD)
        self._list_win = self._list_canvas.create_window(
            (0, 0), window=self._list_frame, anchor="nw")

        self._list_frame.bind("<Configure>", lambda e: self._list_canvas.configure(
            scrollregion=self._list_canvas.bbox("all")))
        self._list_canvas.bind("<MouseWheel>",
            lambda e: self._list_canvas.yview_scroll(
                int(-1 * e.delta / 120), "units"))

        self._placeholder = label(
            self._list_frame,
            "Chargez un fichier et sélectionnez une période.",
            font=F_SMALL, fg=MUTED, bg=CARD, pady=24,
        )
        self._placeholder.pack()

    # ── Actions (generate + progress) ─────────────────────────────────────────

    def _build_actions(self, parent, row):
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=row, column=0, sticky="ew", pady=(12, 0))
        frame.columnconfigure(0, weight=1)

        # Generate button — centered
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.grid(row=0, column=0)  # pas sticky="ew" → centré naturellement

        self._btn_gen = tk.Button(
            btn_frame,
            text="Générer les PDF sélectionnés",
            command=self._start,
            bg=ACCENT_D, fg="#FFFFFF",
            relief="flat", bd=0, font=F_BOLD,
            padx=20, pady=10,
            state="disabled", cursor="arrow",
        )
        self._btn_gen.pack(side="left", padx=(0, 10))

        self._btn_open = tk.Button(
            btn_frame,
            text="↗  Ouvrir le dossier output",
            command=self._open_output,
            bg=BORDER, fg=MUTED, font=F_BOLD,
            relief="solid", bd=1, padx=12, pady=9,
            state="disabled", cursor="arrow",
        )
        self._btn_open.pack(side="left")

        # Progress
        prog = tk.Frame(frame, bg=BG)
        prog.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        prog.columnconfigure(0, weight=1)

        self._progress = ttk.Progressbar(
            prog, orient="horizontal", mode="determinate",
            style="App.Horizontal.TProgressbar")
        self._progress.grid(row=0, column=0, sticky="ew")

        self._prog_label = tk.Label(
            prog, text="", font=F_SMALL, fg=MUTED, bg=BG, width=14, anchor="e")
        self._prog_label.grid(row=0, column=1, padx=(8, 0))

    # ── Log ───────────────────────────────────────────────────────────────────

    def _build_log(self, parent, row):
        frame = tk.Frame(parent, bg=LOG_BG, bd=1, relief="solid",
                         highlightbackground=BORDER, highlightthickness=0)
        frame.grid(row=row, column=0, sticky="ew", pady=(12, 0))
        frame.columnconfigure(0, weight=1)

        self._log = tk.Text(
            frame, height=5, state="disabled",
            bg=LOG_BG, fg=LOG_FG, font=F_MONO,
            relief="flat", padx=12, pady=8,
            wrap="none",
        )
        self._log.pack(side="left", fill="both", expand=True)
        self._log.tag_configure("ok",   foreground=LOG_OK)
        self._log.tag_configure("err",  foreground=LOG_ERR)
        self._log.tag_configure("info", foreground=LOG_INFO)

        sb = ttk.Scrollbar(frame, command=self._log.yview)
        sb.pack(side="right", fill="y")
        self._log.configure(yscrollcommand=sb.set)

    # ── Checklist helpers ─────────────────────────────────────────────────────

    def _check_all(self):
        for v in self._check_vars:
            v.set(True)
        self._refresh_colors()
        self._update_sel()

    def _uncheck_all(self):
        for v in self._check_vars:
            v.set(False)
        self._refresh_colors()
        self._update_sel()

    def _on_toggle(self, idx):
        self._refresh_color(idx)
        self._update_sel()

    def _row_bg(self, idx):
        if self._check_vars[idx].get():
            return ROW_SEL
        return ROW_ODD if idx % 2 else ROW_EVEN

    def _refresh_color(self, idx):
        bg = self._row_bg(idx)
        self._check_widgets[idx].configure(bg=bg, activebackground=bg, selectcolor=bg)

    def _refresh_colors(self):
        for i in range(len(self._check_vars)):
            self._refresh_color(i)

    def _update_sel(self):
        n = sum(v.get() for v in self._check_vars)
        total = len(self._check_vars)
        if total == 0:
            self._sel_label.config(text="—", fg=MUTED)
        else:
            self._sel_label.config(
                text=f"{n} / {total} sélectionnée(s)",
                fg=ACCENT if n else MUTED,
            )
        if n > 0:
            self._btn_gen.config(state="normal", bg=ACCENT, cursor="hand2")
        else:
            self._btn_gen.config(state="disabled", bg=ACCENT_D, cursor="arrow")

    def _clear_list(self):
        for w in self._check_widgets:
            w.destroy()
        if hasattr(self, "_placeholder") and self._placeholder.winfo_exists():
            self._placeholder.destroy()
        self._check_vars.clear()
        self._check_widgets.clear()

    # ── Load ──────────────────────────────────────────────────────────────────

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Sélectionner le fichier missions",
            filetypes=[("Excel", "*.xlsx")],
        )
        if path:
            self._xlsx_path.set(path)

    def _load_missions(self):
        xlsx  = self._xlsx_path.get()
        lbl   = self._sheet_var.get()
        if not xlsx:
            messagebox.showwarning("Fichier manquant",
                                   "Veuillez sélectionner un fichier Excel.")
            return
        if not lbl:
            messagebox.showwarning("Période manquante",
                                   "Veuillez choisir une période.")
            return

        sheet = VALID_SHEETS[[SHEET_LABELS[s] for s in VALID_SHEETS].index(lbl)]
        try:
            df = pd.read_excel(xlsx, sheet_name=sheet)
            # Track Excel row BEFORE any filtering (header = row 1, data starts row 2)
            df["_excel_row"] = range(2, len(df) + 2)
            df = df.drop(columns=["nom_jeune"], errors="ignore")
            df = df.dropna(subset=["h_debut", "h_fin", "description"])
            df = df.reset_index(drop=True)
        except Exception as e:
            messagebox.showerror("Erreur de lecture", str(e))
            return

        self._df = df
        self._xlsx_str = xlsx   # keep for write-back
        self._sheet_name = sheet
        m = re.match(r"(\d{4})-suivi-missions", Path(xlsx).name)
        self._year = m.group(1) if m else "0000"

        self._clear_list()
        self._btn_open.grid_remove()

        for idx, (_, row) in enumerate(df.iterrows()):
            var = tk.BooleanVar(value=False)
            self._check_vars.append(var)

            date_str = format_date_display(row["date"])
            desc = str(row["description"])
            line = f"  {date_str}   {str(row['h_debut'])}-{str(row['h_fin'])}   {desc}"

            bg = ROW_ODD if idx % 2 else ROW_EVEN
            cb = tk.Checkbutton(
                self._list_frame,
                text=line, variable=var,
                anchor="w", font=F_MONO,
                bg=bg, activebackground=bg,
                fg=TEXT, selectcolor=bg,
                relief="flat", bd=0,
                command=lambda i=idx: self._on_toggle(i),
            )
            cb.pack(fill="x", padx=0, pady=0)
            self._check_widgets.append(cb)

        self._update_sel()
        self._log_clear()
        self._log_write(("info", f"Chargé : {len(df)} mission(s) — {lbl}\n"))

    # ── Generate ──────────────────────────────────────────────────────────────

    def _start(self):
        if self._df is None or not self._check_vars:
            return
        lbl   = self._sheet_var.get()
        sheet = VALID_SHEETS[[SHEET_LABELS[s] for s in VALID_SHEETS].index(lbl)]
        rows  = [self._df.iloc[i]
                 for i, v in enumerate(self._check_vars) if v.get()]
        if not rows:
            return

        self._btn_gen.config(state="disabled", bg=ACCENT_D, cursor="arrow")
        self._btn_open.config(state="disabled", bg=BORDER, fg=MUTED, cursor="arrow")
        self._progress["value"] = 0
        self._prog_label.config(text="")
        self._log_clear()

        threading.Thread(
            target=self._run,
            args=(rows, self._year, sheet, self._xlsx_str),
            daemon=True).start()

    def _run(self, rows, year, sheet, xlsx_path):
        try:
            out_dir = generate(rows, year, sheet, xlsx_path,
                               self._log_queue.put, self._queue_progress)
            self._out_dir = out_dir
            self._log_queue.put("__DONE__")
        except Exception as e:
            self._log_queue.put(("err", f"\nERREUR : {e}\n"))
            self._log_queue.put("__ERR__")

    def _queue_progress(self, cur, tot):
        self._log_queue.put(("__PROGRESS__", cur, tot))

    # ── Polling ───────────────────────────────────────────────────────────────

    def _poll_log(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                if msg == "__DONE__":
                    self._uncheck_all()
                    self._btn_open.config(
                        state="normal", bg=CARD, fg=ACCENT, cursor="hand2")
                elif msg == "__ERR__":
                    self._update_sel()
                elif isinstance(msg, tuple) and msg[0] == "__PROGRESS__":
                    _, cur, tot = msg
                    pct = int(cur / tot * 100) if tot else 0
                    self._progress["maximum"] = tot
                    self._progress["value"]   = cur
                    self._prog_label.config(text=f"{cur}/{tot}  {pct}%")
                else:
                    self._log_write(msg)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _log_write(self, msg):
        tag, text = msg if isinstance(msg, tuple) else ("info", msg)
        self._log.configure(state="normal")
        self._log.insert("end", text, tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _log_clear(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _open_output(self):
        if self._out_dir and self._out_dir.exists():
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(self._out_dir)])
            else:
                subprocess.Popen(["xdg-open", str(self._out_dir)])


if __name__ == "__main__":
    App().mainloop()
