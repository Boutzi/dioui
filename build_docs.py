"""Génère docs/Dioui-documentation.pdf depuis README.md."""
import re
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Preformatted, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BLUE      = colors.HexColor("#1F4E79")
ACCENT    = colors.HexColor("#3B82F6")
BG_CODE   = colors.HexColor("#0f172a")
FG_CODE   = colors.HexColor("#e2e8f0")
BG_QUOTE  = colors.HexColor("#f0f6ff")
BG_EVEN   = colors.HexColor("#f8fafc")
TEXT      = colors.HexColor("#1a1a2e")
TEXT_SUB  = colors.HexColor("#475569")
BORDER    = colors.HexColor("#cbd5e1")

W, H = A4
ML = 22*mm; MR = 22*mm; MT = 20*mm; MB = 20*mm

def styles():
    base = dict(fontName="Helvetica", fontSize=10, leading=15, textColor=TEXT, spaceAfter=4)
    return {
        "h1":    ParagraphStyle("h1",    fontName="Helvetica-Bold", fontSize=22, textColor=BLUE,    spaceAfter=6,  spaceBefore=0,  leading=26),
        "h2":    ParagraphStyle("h2",    fontName="Helvetica-Bold", fontSize=14, textColor=BLUE,    spaceAfter=4,  spaceBefore=18, leading=18),
        "h3":    ParagraphStyle("h3",    fontName="Helvetica-Bold", fontSize=11, textColor=TEXT,    spaceAfter=4,  spaceBefore=12, leading=14),
        "body":  ParagraphStyle("body",  **base),
        "quote": ParagraphStyle("quote", fontName="Helvetica-Oblique", fontSize=10, textColor=BLUE,
                                backColor=BG_QUOTE, borderPadding=(8,12,8,12), spaceAfter=8, leading=15),
        "li":    ParagraphStyle("li",    **{**base, "leftIndent": 14, "spaceAfter": 3}),
        "code":  ParagraphStyle("code",  fontName="Courier", fontSize=9,  textColor=FG_CODE,
                                backColor=BG_CODE,  borderPadding=(10,14,10,14), spaceAfter=8, leading=13),
        "sub":   ParagraphStyle("sub",   fontName="Helvetica-Oblique", fontSize=10, textColor=TEXT_SUB, spaceAfter=8, leading=14),
    }

def parse_inline(text):
    text = re.sub(r"`([^`]+)`", r'<font face="Courier" color="#1e3a5f" backColor="#f1f5f9"> \1 </font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return text

def build_pdf(src="README.md", dst="docs/Dioui-documentation.pdf"):
    Path("docs").mkdir(exist_ok=True)
    s = styles()
    doc = SimpleDocTemplate(dst, pagesize=A4,
                            leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
                            title="Dioui — Documentation")

    lines = Path(src).read_text(encoding="utf-8").splitlines()
    story = []
    i = 0
    in_code = False
    code_buf = []

    def flush_code():
        nonlocal code_buf
        story.append(Preformatted("\n".join(code_buf), s["code"]))
        story.append(Spacer(1, 4))
        code_buf = []

    table_buf = []
    in_table = False

    def flush_table():
        nonlocal table_buf
        if not table_buf:
            return
        col_count = len(table_buf[0])
        col_w = (W - ML - MR) / col_count
        ts = TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), BLUE),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, BG_EVEN]),
            ("GRID",        (0,0), (-1,-1), 0.5, BORDER),
            ("LEFTPADDING",  (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING",   (0,0), (-1,-1), 6),
            ("BOTTOMPADDING",(0,0), (-1,-1), 6),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ])
        t = Table([[Paragraph(c.strip(), s["body"]) for c in row] for row in table_buf],
                  colWidths=[col_w]*col_count)
        t.setStyle(ts)
        story.append(t)
        story.append(Spacer(1, 8))
        table_buf.clear()

    while i < len(lines):
        line = lines[i]

        # fenced code block
        if line.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # table
        if "|" in line and line.strip().startswith("|"):
            row = [c for c in line.strip().strip("|").split("|")]
            # skip separator row
            if all(re.match(r"[-: ]+$", c.strip()) for c in row):
                i += 1
                continue
            table_buf.append(row)
            in_table = True
            i += 1
            continue
        else:
            if in_table:
                flush_table()
                in_table = False

        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 6))
            i += 1
            continue

        if stripped.startswith("# ") and not stripped.startswith("## "):
            story.append(Paragraph(stripped[2:], s["h1"]))
            story.append(HRFlowable(width="100%", thickness=3, color=ACCENT, spaceAfter=6))
            i += 1
            continue

        if stripped.startswith("## "):
            flush_table()
            story.append(Spacer(1, 4))
            story.append(Paragraph(stripped[3:], s["h2"]))
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=4))
            i += 1
            continue

        if stripped.startswith("### "):
            story.append(Paragraph(stripped[4:], s["h3"]))
            i += 1
            continue

        if stripped.startswith("---"):
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=8, spaceAfter=8))
            i += 1
            continue

        if stripped.startswith("> "):
            story.append(Paragraph(parse_inline(stripped[2:]), s["quote"]))
            i += 1
            continue

        if stripped.startswith("- "):
            story.append(Paragraph("• " + parse_inline(stripped[2:]), s["li"]))
            i += 1
            continue

        if re.match(r"^\d+\.", stripped):
            text = re.sub(r"^\d+\.\s*", "", stripped)
            story.append(Paragraph("• " + parse_inline(text), s["li"]))
            i += 1
            continue

        story.append(Paragraph(parse_inline(stripped), s["body"]))
        i += 1

    if in_code:
        flush_code()
    if in_table:
        flush_table()

    doc.build(story)
    print(f"PDF généré : {dst}")

if __name__ == "__main__":
    build_pdf()
