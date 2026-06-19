import sys
import re
import unicodedata
import subprocess
import threading
import queue
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR   = Path(__file__).parent.parent
DOCS_DIR   = BASE_DIR / "docs"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_PATH  = ASSETS_DIR / "image1.png"

VALID_SHEETS = ["missions_hiver", "missions_printemps", "missions_ete", "missions_automne"]
SHEET_LABELS = {
    "missions_hiver":     "Hiver",
    "missions_printemps": "Printemps",
    "missions_ete":       "Ete",
    "missions_automne":   "Automne",
}

# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# PDF generation (reportlab — single page guaranteed)
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = A4          # 595 x 842 pt
MARGIN_L = 18 * mm
MARGIN_R = 18 * mm
MARGIN_T = 18 * mm
MARGIN_B = 18 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

LABEL_W  = 38 * mm
VALUE_W  = CONTENT_W - LABEL_W
ROW_H    = 9 * mm
FONT_REG = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _fit_font_size(c, text, max_width, start_size=10, min_size=6):
    size = start_size
    while size >= min_size:
        if c.stringWidth(text, FONT_REG, size) <= max_width:
            return size
        size -= 0.5
    return min_size


def _draw_wrapped_text_in_box(c, text, x, y, max_w, box_h, font_size):
    """Draw text wrapped inside a box of fixed height; shrinks font if needed."""
    from reportlab.lib.utils import simpleSplit
    line_h = font_size * 1.3

    # Try current font size; shrink until lines fit in box_h
    size = font_size
    while size >= 6:
        lines = simpleSplit(text, FONT_REG, size, max_w)
        if len(lines) * (size * 1.3) <= box_h - 2:
            break
        size -= 0.5

    c.setFont(FONT_REG, size)
    line_h = size * 1.3
    text_y = y + box_h - size - 2
    for line in lines:
        if text_y < y:
            break
        c.drawString(x, text_y, line)
        text_y -= line_h


def generate_pdf(row, out_path):
    date_str    = format_date_display(row["date"])
    heure_str   = f"{row['h_debut']}-{row['h_fin']}"
    description = str(row.get("description", ""))
    lieu_rdv    = str(row.get("lieu_rdv", ""))
    referent    = str(row.get("referent", ""))
    contact     = str(row.get("contact", ""))

    c = canvas.Canvas(str(out_path), pagesize=A4)

    y = PAGE_H - MARGIN_T

    # --- Logo ---
    if LOGO_PATH.exists():
        logo_size = 22 * mm
        c.drawImage(ImageReader(str(LOGO_PATH)),
                    MARGIN_L, y - logo_size,
                    width=logo_size, height=logo_size,
                    preserveAspectRatio=True, mask="auto")

    # --- Titles ---
    title_x = MARGIN_L + 26 * mm
    c.setFont(FONT_BOLD, 14)
    c.drawCentredString(PAGE_W / 2, y - 8 * mm, "MISSION ARGENT DE POCHE")
    c.setFont(FONT_BOLD, 12)
    c.drawCentredString(PAGE_W / 2, y - 15 * mm, "ATTESTATION D'INDEMNISATION")

    y -= 28 * mm

    # --- Nom / Prénom ---
    c.setFont(FONT_BOLD, 10)
    c.drawString(MARGIN_L, y, "Nom :                                        Prénom :")
    y -= 5 * mm

    # --- Separator line ---
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, y, MARGIN_L + CONTENT_W, y)
    y -= 6 * mm

    # --- Table rows (label | value) ---
    ROWS = [
        ("Date",        date_str,    ROW_H),
        ("Heure",       heure_str,   ROW_H),
        ("Missions",    description, 28 * mm),   # taller row for long text
        ("Lieu de RDV", lieu_rdv,    ROW_H),
        ("Référent",    referent,    ROW_H),
        ("Contact",     contact,     ROW_H),
    ]

    border_color = colors.HexColor("#333333")
    label_bg     = colors.HexColor("#f0f0f0")

    for label, value, row_h in ROWS:
        lx = MARGIN_L
        vx = MARGIN_L + LABEL_W

        # Label cell background
        c.setFillColor(label_bg)
        c.rect(lx, y - row_h, LABEL_W, row_h, fill=1, stroke=0)

        # Borders
        c.setStrokeColor(border_color)
        c.setLineWidth(0.4)
        c.setFillColor(colors.white)
        c.rect(lx, y - row_h, LABEL_W, row_h, fill=0, stroke=1)
        c.rect(vx, y - row_h, VALUE_W, row_h, fill=1, stroke=1)

        # Label text
        c.setFillColor(colors.black)
        c.setFont(FONT_BOLD, 9)
        c.drawString(lx + 2 * mm, y - row_h / 2 - 1.5, label)

        # Value text
        if label == "Missions":
            _draw_wrapped_text_in_box(c, value, vx + 2 * mm, y - row_h, VALUE_W - 4 * mm, row_h, 9)
        else:
            fs = _fit_font_size(c, value, VALUE_W - 4 * mm)
            c.setFont(FONT_REG, fs)
            c.drawString(vx + 2 * mm, y - row_h / 2 - 1.5, value)

        y -= row_h

    y -= 4 * mm

    # --- Separator line ---
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, y, MARGIN_L + CONTENT_W, y)
    y -= 6 * mm

    # --- Fait le ---
    c.setFont(FONT_BOLD, 10)
    c.setFillColor(colors.HexColor("#1F4E79"))
    c.drawString(MARGIN_L, y, "Fait le :           /           /")
    y -= 8 * mm

    # --- Horaires respectés ---
    c.drawString(MARGIN_L, y, "Horaires respectés :")
    # Checkboxes
    box_y = y - 1.5
    box_size = 8

    oui_x = MARGIN_L + 58 * mm
    c.setStrokeColor(colors.HexColor("#1F4E79"))
    c.setFillColor(colors.white)
    c.rect(oui_x, box_y, box_size, box_size, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#1F4E79"))
    c.drawString(oui_x + 11, y, "Oui")

    non_x = oui_x + 28 * mm
    c.setFillColor(colors.white)
    c.rect(non_x, box_y, box_size, box_size, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#1F4E79"))
    c.drawString(non_x + 11, y, "Non")

    c.save()


# ---------------------------------------------------------------------------
# Generation orchestrator
# ---------------------------------------------------------------------------

def generate(xlsx_path, sheet, year, log_fn, progress_fn):
    df = pd.read_excel(xlsx_path, sheet_name=sheet)
    df = df.drop(columns=["nom_jeune"], errors="ignore")
    df = df.dropna(subset=["h_debut", "h_fin", "description"])

    out_dir = OUTPUT_DIR / year / sheet
    out_dir.mkdir(parents=True, exist_ok=True)

    total = len(df)
    log_fn(f"{total} mission(s) trouvée(s)\n")
    progress_fn(0, total)

    for i, (_, row) in enumerate(df.iterrows(), 1):
        date_slug  = format_date_slug(row["date"])
        heure_slug = f"{row['h_debut']}-{row['h_fin']}"
        lieu_slug  = slugify(str(row["lieu_rdv"]))
        filename   = f"{date_slug}_{heure_slug}_{lieu_slug}.pdf"
        pdf_path   = out_dir / filename

        try:
            generate_pdf(row, pdf_path)
            log_fn(f"[{i}/{total}] OK  {filename}\n")
        except Exception as e:
            log_fn(f"[{i}/{total}] ERR {filename} : {e}\n")

        progress_fn(i, total)

    log_fn(f"\nTerminé. Dossier : {out_dir}\n")
    return out_dir


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Missions Argent de Poche — Génération PDF")
        self.resizable(False, False)
        self.configure(padx=20, pady=20)

        self._xlsx_path  = tk.StringVar()
        self._sheet_var  = tk.StringVar()
        self._log_queue  = queue.Queue()
        self._out_dir    = None

        self._build_ui()
        self._poll_log()

    def _build_ui(self):
        # --- Fichier ---
        tk.Label(self, text="Fichier Excel :", anchor="w").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        frame_file = tk.Frame(self)
        frame_file.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        tk.Entry(frame_file, textvariable=self._xlsx_path, width=52, state="readonly").pack(side="left", padx=(0, 8))
        tk.Button(frame_file, text="Parcourir...", command=self._browse).pack(side="left")

        # --- Période ---
        tk.Label(self, text="Période de vacances :", anchor="w").grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self._combo = ttk.Combobox(
            self,
            textvariable=self._sheet_var,
            values=[SHEET_LABELS[s] for s in VALID_SHEETS],
            state="readonly",
            width=20,
        )
        self._combo.grid(row=3, column=0, sticky="w", pady=(0, 12))

        # --- Bouton générer ---
        self._btn = tk.Button(
            self, text="Générer les PDF", command=self._start,
            bg="#2563eb", fg="white", font=("", 11, "bold"), padx=12, pady=6,
        )
        self._btn.grid(row=4, column=0, sticky="w", pady=(0, 8))

        # --- Barre de progression ---
        self._progress = ttk.Progressbar(self, orient="horizontal", length=460, mode="determinate")
        self._progress.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self._progress_label = tk.Label(self, text="", anchor="w", fg="#555555")
        self._progress_label.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 4))

        # --- Log ---
        tk.Label(self, text="Progression :", anchor="w").grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self._log = tk.Text(
            self, width=70, height=16, state="disabled",
            bg="#1e1e1e", fg="#d4d4d4", font=("Courier", 9),
        )
        self._log.grid(row=8, column=0, sticky="ew")

        scroll = ttk.Scrollbar(self, command=self._log.yview)
        scroll.grid(row=8, column=1, sticky="ns")
        self._log.configure(yscrollcommand=scroll.set)

        # --- Bouton ouvrir dossier (caché jusqu'à la fin) ---
        self._btn_open = tk.Button(self, text="Ouvrir le dossier output", command=self._open_output)
        self._btn_open.grid(row=9, column=0, sticky="w", pady=(8, 0))
        self._btn_open.grid_remove()

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Sélectionner le fichier missions",
            filetypes=[("Excel", "*.xlsx")],
        )
        if path:
            self._xlsx_path.set(path)

    def _start(self):
        xlsx  = self._xlsx_path.get()
        label = self._sheet_var.get()

        if not xlsx:
            messagebox.showwarning("Fichier manquant", "Veuillez sélectionner un fichier Excel.")
            return
        if not label:
            messagebox.showwarning("Période manquante", "Veuillez choisir une période de vacances.")
            return

        sheet = VALID_SHEETS[[SHEET_LABELS[s] for s in VALID_SHEETS].index(label)]
        year_match = re.match(r"(\d{4})-suivi-missions", Path(xlsx).name)
        if not year_match:
            messagebox.showerror("Nom invalide", "Le fichier doit se nommer YYYY-suivi-missions-argent-de-poche.xlsx")
            return
        year = year_match.group(1)

        self._btn.config(state="disabled")
        self._btn_open.grid_remove()
        self._progress["value"] = 0
        self._progress_label.config(text="")
        self._log_clear()

        threading.Thread(target=self._run, args=(xlsx, sheet, year), daemon=True).start()

    def _run(self, xlsx, sheet, year):
        try:
            out_dir = generate(xlsx, sheet, year, self._log_queue.put, self._queue_progress)
            self._out_dir = out_dir
            self._log_queue.put("__DONE__")
        except Exception as e:
            self._log_queue.put(f"\nERREUR : {e}\n")
            self._log_queue.put("__ERR__")

    def _queue_progress(self, current, total):
        self._log_queue.put(("__PROGRESS__", current, total))

    def _poll_log(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                if msg == "__DONE__":
                    self._btn.config(state="normal")
                    self._btn_open.grid()
                elif msg == "__ERR__":
                    self._btn.config(state="normal")
                elif isinstance(msg, tuple) and msg[0] == "__PROGRESS__":
                    _, current, total = msg
                    pct = int(current / total * 100) if total else 0
                    self._progress["maximum"] = total
                    self._progress["value"]   = current
                    self._progress_label.config(text=f"{current} / {total}  ({pct}%)")
                else:
                    self._log_write(msg)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _log_write(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text)
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
