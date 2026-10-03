# src/ai_exporter.py
"""Exportadores con diseño corporativo usando office-worker-mcp."""
import io
import re
from pathlib import Path
from datetime import datetime

from office_worker import core


def _tema_niah():
    """Tema con los colores de NIAH: azul Apple + verde salud."""
    return core.Theme(
        name="niah",
        primary="#0A84FF",
        accent="#34C759",
        text="#1D1D1F",
        muted="#6E6E73",
        row_alt="#F5F5F7",
        bg="#FFFFFF",
        font_title="Inter, -apple-system, sans-serif",
        font_body="Inter, -apple-system, sans-serif",
    )


def _extraer_titulo(md: str) -> str:
    """Primera línea no vacía sin marcas markdown, máx 80 chars."""
    for linea in md.split("\n"):
        limpia = linea.strip().lstrip("#").strip()
        if limpia:
            return limpia[:80]
    return "Respuesta de NIAH"


def _parse_bloques(md: str) -> list[dict]:
    """Convierte markdown a bloques estructurados para office-worker."""
    bloques = []
    lineas = md.split("\n")
    i = 0
    while i < len(lineas):
        l = lineas[i]
        if l.startswith("### "):
            bloques.append({"type": "h3", "text": l[4:].strip()})
        elif l.startswith("## "):
            bloques.append({"type": "h2", "text": l[3:].strip()})
        elif l.startswith("# "):
            bloques.append({"type": "h1", "text": l[2:].strip()})
        elif re.match(r"^\s*[\-\*]\s+", l):
            bloques.append({"type": "li", "text": re.sub(r"^\s*[\-\*]\s+", "", l)})
        elif l.strip().startswith("|") and l.strip().endswith("|"):
            filas = []
            while i < len(lineas) and lineas[i].strip().startswith("|"):
                f = lineas[i].strip()
                if not re.match(r"^\|[\s\-:|]+\|$", f):
                    filas.append([c.strip() for c in f.strip("|").split("|")])
                i += 1
            if filas:
                bloques.append({
                    "type": "table",
                    "headers": filas[0],
                    "rows": filas[1:] if len(filas) > 1 else [],
                })
            continue
        elif l.strip():
            bloques.append({"type": "p", "text": l})
        i += 1
    return bloques


def _strip_inline(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", s)
    return s
def _a_pdf(titulo: str, subtitulo: str, bloques: list[dict], out_path: str) -> str:
    """PDF con plantilla HTML embebida + tema NIAH."""
    partes_html = []
    for b in bloques:
        t = b.get("type")
        if t == "h1":
            partes_html.append(f"<h1>{_strip_inline(b['text'])}</h1>")
        elif t == "h2":
            partes_html.append(f"<h2>{_strip_inline(b['text'])}</h2>")
        elif t == "h3":
            partes_html.append(f"<h3>{_strip_inline(b['text'])}</h3>")
        elif t == "li":
            partes_html.append(f"<li>{_strip_inline(b['text'])}</li>")
        elif t == "table":
            heads = "".join(f"<th>{_strip_inline(c)}</th>" for c in b.get("headers", []))
            filas = "".join(
                "<tr>" + "".join(f"<td>{_strip_inline(c)}</td>" for c in fila) + "</tr>"
                for fila in b.get("rows", [])
            )
            partes_html.append(f"<table><thead><tr>{heads}</tr></thead><tbody>{filas}</tbody></table>")
        elif t == "p":
            partes_html.append(f"<p>{_strip_inline(b['text'])}</p>")

    cuerpo = "\n".join(partes_html)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body>
  <header class="niah-header">
    <div class="niah-brand">NIAH</div>
    <div class="niah-meta">{datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
  </header>
  <h1 class="niah-title">{titulo}</h1>
  {f'<p class="niah-subtitle">{subtitulo}</p>' if subtitulo else ''}
  <main class="niah-body">{cuerpo}</main>
  <footer class="niah-footer">Generado por NIAH · Neural Intelligent Assistant Hub</footer>
</body>
</html>"""

    core.render_pdf(
        template_html_or_path=html,
        out_path=out_path,
        data={},
        theme=_tema_niah(),
        page_numbers=True,
        footer_left="NIAH",
        footer_right=datetime.now().strftime("%Y-%m-%d"),
        design_mode="premium",
    )
    return out_path


def _a_docx(titulo: str, subtitulo: str, bloques: list[dict], out_path: str) -> str:
    core.create_word(
        out_path=out_path,
        title=titulo,
        subtitle=subtitulo or None,
        blocks=bloques,
        theme=_tema_niah(),
    )
    return out_path


def _a_xlsx(titulo: str, subtitulo: str, bloques: list[dict], out_path: str) -> str:
    """Hoja 1: portada con título. Hoja 2+: contenido estructurado."""
    filas = []
    for b in bloques:
        t = b.get("type")
        if t in ("h1", "h2", "h3"):
            filas.append([_strip_inline(b["text"])])
        elif t == "li":
            filas.append(["• " + _strip_inline(b["text"])])
        elif t == "table":
            filas.append([" | ".join(_strip_inline(c) for c in b.get("headers", []))])
            for fila in b.get("rows", []):
                filas.append([" | ".join(_strip_inline(c) for c in fila)])
        elif t == "p":
            filas.append([_strip_inline(b["text"])])

    core.create_excel(
        out_path=out_path,
        title=titulo,
        kicker=subtitulo or None,
        sheets=[{
            "name": "Contenido",
            "rows": filas,
        }],
        theme=_tema_niah(),
    )
    return out_path
def _a_pptx(titulo: str, subtitulo: str, bloques: list[dict], out_path: str) -> str:
    """Convierte bloques en slides. Cada h1/h2 abre slide nuevo."""
    slides = [{
        "title": titulo,
        "kicker": subtitulo or "Respuesta de NIAH",
        "bullets": [datetime.now().strftime("Generado el %d/%m/%Y a las %H:%M")],
    }]

    slide_actual = None
    for b in bloques:
        t = b.get("type")
        if t in ("h1", "h2"):
            if slide_actual:
                slides.append(slide_actual)
            slide_actual = {"title": _strip_inline(b["text"]), "bullets": []}
        elif t == "h3":
            if slide_actual is None:
                slide_actual = {"title": "Contenido", "bullets": []}
            slide_actual["bullets"].append(f"**{_strip_inline(b['text'])}**")
        elif t == "li":
            if slide_actual is None:
                slide_actual = {"title": "Contenido", "bullets": []}
            slide_actual["bullets"].append(_strip_inline(b["text"]))
        elif t == "p":
            if slide_actual is None:
                slide_actual = {"title": "Contenido", "bullets": []}
            texto = _strip_inline(b["text"])
            if texto:
                slide_actual["bullets"].append(texto[:180])
        elif t == "table" and b.get("headers"):
            if slide_actual is None:
                slide_actual = {"title": "Tabla", "bullets": []}
            heads = " | ".join(_strip_inline(c) for c in b["headers"])
            slide_actual["bullets"].append(f"📊 {heads}")
            for fila in b.get("rows", [])[:5]:
                slide_actual["bullets"].append("  · " + " | ".join(_strip_inline(c) for c in fila))
        if slide_actual and len(slide_actual.get("bullets", [])) >= 7:
            slides.append(slide_actual)
            slide_actual = None
    if slide_actual:
        slides.append(slide_actual)

    core.create_pptx(
        out_path=out_path,
        slides=slides,
        theme=_tema_niah(),
        prefer_native=True,
    )
    return out_path


def exportar_estilizado(formato: str, titulo: str, contenido: str,
                        subtitulo: str = "", out_dir: str = "/tmp") -> tuple[bytes, str, str]:
    """Devuelve (bytes, mime, ext) usando office-worker para PDF/DOCX/XLSX/PPTX."""
    formato = formato.lower()
    bloques = _parse_bloques(contenido)
    ts = int(datetime.now().timestamp() * 1000)
    out_path = str(Path(out_dir) / f"niah_{ts}.{formato}")

    if formato == "pdf":
        _a_pdf(titulo, subtitulo, bloques, out_path)
        mime = "application/pdf"
    elif formato == "docx":
        _a_docx(titulo, subtitulo, bloques, out_path)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif formato == "xlsx":
        _a_xlsx(titulo, subtitulo, bloques, out_path)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif formato == "pptx":
        _a_pptx(titulo, subtitulo, bloques, out_path)
        mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        raise ValueError(f"Formato no soportado por office-worker: {formato}")

    data = Path(out_path).read_bytes()
    return data, mime, formato
def exportar_con_diseno(formato: str, titulo: str, contenido: str,
                        subtitulo: str = "") -> tuple[bytes, str, str]:
    """
    Punto de entrada principal.
    - PDF/DOCX/XLSX/PPTX → office-worker con tema NIAH
    - MD/HTML/TXT/JSON   → fallback a src.exporters (sin office-worker)
    """
    if formato.lower() in ("pdf", "docx", "xlsx", "pptx"):
        return exportar_estilizado(formato, titulo, contenido, subtitulo)
    # Fallback a generadores simples
    from src.exporters import exportar as exportar_simple
    return exportar_simple(formato, titulo, contenido)


def limpiar_temporales(max_age_min: int = 60) -> int:
    """Borra archivos niah_*.{pdf,docx,xlsx,pptx} de /tmp más viejos que max_age_min."""
    import time
    ahora = time.time()
    borrados = 0
    for ext in ("pdf", "docx", "xlsx", "pptx"):
        for f in Path("/tmp").glob(f"niah_*.{ext}"):
            if ahora - f.stat().st_mtime > max_age_min * 60:
                try:
                    f.unlink()
                    borrados += 1
                except Exception:
                    pass
    return borrados

