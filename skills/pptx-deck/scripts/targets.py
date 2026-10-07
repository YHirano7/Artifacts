"""Output-target compatibility checks (PowerPoint / Google Slides).

The build always writes .pptx. When the deck will be opened in Google Slides
(Drive upload → "Open with Google Slides"), a few things degrade on import.
This module lists them so the build report can say so up front instead of
the reviewer finding out after conversion.
"""
from pptx.oxml.ns import qn

from common import read_theme

TARGETS = ("powerpoint", "google_slides")

# Fonts known to be selectable in Google Slides (Google Fonts plus the
# Microsoft-compatible faces Google provides). Anything else is substituted
# on import. This is a known-good list, not an exhaustive one: a font missing
# here is reported as "要確認", not as a hard error.
GOOGLE_SLIDES_FONTS = {
    # Japanese
    "Noto Sans JP", "Noto Serif JP", "BIZ UDPGothic", "BIZ UDGothic",
    "BIZ UDPMincho", "BIZ UDMincho", "M PLUS 1p", "M PLUS 1", "M PLUS 2",
    "M PLUS Rounded 1c", "Sawarabi Gothic", "Sawarabi Mincho", "Kosugi",
    "Kosugi Maru", "Zen Kaku Gothic New", "Zen Maru Gothic", "Murecho",
    "IBM Plex Sans JP", "Shippori Mincho", "Kiwi Maru",
    # Latin
    "Arial", "Calibri", "Cambria", "Georgia", "Times New Roman", "Verdana",
    "Trebuchet MS", "Courier New", "Comic Sans MS", "Roboto", "Open Sans",
    "Lato", "Montserrat", "Inter", "Source Sans 3", "Noto Sans",
}


def _used_typefaces(prs, slides):
    faces = set()
    theme = read_theme(prs)["fonts"]
    for group in theme.values():
        faces.update(v for v in group.values() if v)
    for slide in slides:
        for tag in ("a:latin", "a:ea"):
            for el in slide._element.iter(qn(tag)):
                face = el.get("typeface", "")
                if face and not face.startswith("+"):
                    faces.add(face)
    return faces


def compat_findings(prs, n_original, target):
    """Return [{slide, message}] for features that degrade on ``target``.

    ``slide`` is the 1-based number in the finished deck (template sample
    slides are dropped after build), or None for deck-wide findings.
    """
    if target != "google_slides":
        return []
    slides = list(prs.slides)[n_original:]
    findings = []
    for number, slide in enumerate(slides, start=1):
        for frame in slide._element.iter(qn("p:graphicFrame")):
            data = frame.find(f".//{qn('a:graphicData')}")
            uri = data.get("uri", "") if data is not None else ""
            if uri.endswith("/chart"):
                findings.append({
                    "slide": number,
                    "message": "グラフはGoogleスライドへの取り込み時に静止画"
                               "になり、データを編集できない。編集が必要なら"
                               "Googleスプレッドシートのグラフを貼り直すか、"
                               "表・KPIなど図形の部品に置き換える"})
    unknown = sorted(f for f in _used_typefaces(prs, slides)
                     if f not in GOOGLE_SLIDES_FONTS)
    if unknown:
        findings.append({
            "slide": None,
            "message": f"フォント {unknown} はGoogleスライドの既知フォントに"
                       "無く、取り込み時に置換される可能性がある（要確認）。"
                       "map の style.fonts に Noto Sans JP 等を指定するか、"
                       "Googleスライドから書き出したテンプレートを使う"})
    return findings
