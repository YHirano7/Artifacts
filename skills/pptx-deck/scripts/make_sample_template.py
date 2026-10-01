#!/usr/bin/env python3
"""Generate the sample-org template.pptx used by the pptx-deck skill.

Fictional organization template "Sample Org": 16:9, Yu Gothic theme fonts,
deep-navy color scheme, one cover + six component sample slides.
"""
import argparse
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

FONT = "Yu Gothic"
NAVY = RGBColor(0x1B, 0x3A, 0x66)
ACCENT = RGBColor(0x3E, 0x7C, 0xB1)
GRAY_TEXT = RGBColor(0x59, 0x5F, 0x6B)
INK = RGBColor(0x20, 0x21, 0x24)
LIGHT_LINE = RGBColor(0xC8, 0xCD, 0xD6)
LIGHT_BG = RGBColor(0xF2, 0xF4, 0xF8)
BAND = RGBColor(0xF3, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def set_run_fonts(run, size=None, bold=None, color=None):
    run.font.name = FONT
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", FONT)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def _bullet_ppr(p, kind, spacing_pt):
    pPr = p._p.get_or_add_pPr()
    pPr.set("marL", "457200")
    pPr.set("indent", "-457200")
    if spacing_pt:
        spc = etree.SubElement(pPr, qn("a:spcAft"))
        pts = etree.SubElement(spc, qn("a:spcPts"))
        pts.set("val", str(int(spacing_pt * 100)))
    bu_font = etree.SubElement(pPr, qn("a:buFont"))
    bu_font.set("typeface", "Arial")
    if kind == "num":
        bu = etree.SubElement(pPr, qn("a:buAutoNum"))
        bu.set("type", "arabicPeriod")
    else:
        bu = etree.SubElement(pPr, qn("a:buChar"))
        bu.set("char", "・")


def add_text(slide, name, x, y, w, h, lines, anchor=MSO_ANCHOR.TOP,
             align=PP_ALIGN.LEFT, bullet=None, spacing=None):
    """lines: list of (text, size, bold, color) tuples -> one paragraph each."""
    box = slide.shapes.add_textbox(x, y, w, h)
    box.name = name
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, (text, size, bold, color) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if bullet:
            _bullet_ppr(p, bullet, spacing)
        run = p.add_run()
        run.text = text
        set_run_fonts(run, size=size, bold=bold, color=color)
    return box


def set_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def edit_theme(prs):
    theme_part = None
    for rel in prs.slide_masters[0].part.rels.values():
        if rel.reltype.endswith("/theme"):
            theme_part = rel.target_part
            break
    if theme_part is None:
        raise RuntimeError("theme part not found")
    root = etree.fromstring(theme_part.blob)
    ns = {"a": A}
    colors = {
        "dk1": "202124", "lt1": "FFFFFF", "dk2": "1B3A66", "lt2": "F2F4F8",
        "accent1": "1B3A66", "accent2": "3E7CB1", "accent3": "8A94A6",
        "accent4": "6B7A90", "accent5": "C8CDD6", "accent6": "E4E8EE",
        "hlink": "3E7CB1", "folHlink": "6B7A90",
    }
    for name, hexv in colors.items():
        el = root.find(f".//a:clrScheme/a:{name}", ns)
        for child in list(el):
            el.remove(child)
        srgb = etree.SubElement(el, qn("a:srgbClr"))
        srgb.set("val", hexv)
    for tag in ("a:majorFont", "a:minorFont"):
        font = root.find(f".//a:fontScheme/{tag}", ns)
        latin = font.find("a:latin", ns)
        latin.set("typeface", FONT)
        ea = font.find("a:ea", ns)
        if ea is None:
            ea = etree.SubElement(font, qn("a:ea"))
        ea.set("typeface", FONT)
        for f in font.findall("a:font", ns):
            f.set("typeface", FONT)
    if hasattr(theme_part, "element"):
        theme_part._element = root
    else:
        theme_part._blob = etree.tostring(root, xml_declaration=True,
                                          encoding="UTF-8", standalone=True)


def layout_bg(layout, scheme_color):
    cSld = layout.element.find(qn("p:cSld"))
    old = cSld.find(qn("p:bg"))
    if old is not None:
        cSld.remove(old)
    bg = etree.fromstring(
        f'<p:bg xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        f'xmlns:a="{A}"><p:bgPr><a:solidFill><a:schemeClr val="{scheme_color}"/>'
        f"</a:solidFill><a:effectLst/></p:bgPr></p:bg>"
    )
    cSld.insert(0, bg)


def white_placeholder_text(layout):
    for ph in layout.placeholders:
        tx = ph._element.find(qn("p:txBody"))
        if tx is None:
            continue
        lst = tx.find(qn("a:lstStyle"))
        if lst is None:
            lst = etree.SubElement(tx, qn("a:lstStyle"))
        lvls = [lst.find(qn(f"a:lvl{i}pPr")) for i in range(1, 10)]
        if not any(lv is not None for lv in lvls):
            lvls = [etree.SubElement(lst, qn("a:lvl1pPr"))]
        for lv in lvls:
            if lv is None:
                continue
            dr = lv.find(qn("a:defRPr"))
            if dr is None:
                dr = etree.SubElement(lv, qn("a:defRPr"))
            for f in dr.findall(qn("a:solidFill")):
                dr.remove(f)
            fill = etree.Element(qn("a:solidFill"))
            clr = etree.SubElement(fill, qn("a:schemeClr"))
            clr.set("val", "lt1")
            dr.insert(0, fill)


_SP_ID = [1000]
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _next_sp_id():
    _SP_ID[0] += 1
    return _SP_ID[0]


def _textbox_xml(sp_id, name, x, y, w, h, inner):
    return (
        f'<p:sp xmlns:p="{P_NS}" xmlns:a="{A}">'
        f'<p:nvSpPr><p:cNvPr id="{sp_id}" name="{name}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/>'
        f'</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
        f'<p:txBody><a:bodyPr wrap="none" lIns="0" tIns="0" rIns="0" bIns="0"/>'
        f'<a:lstStyle/>{inner}</p:txBody></p:sp>'
    )


def _rpr(color_hex, sz=900):
    return (
        f'<a:rPr lang="ja-JP" sz="{sz}">'
        f'<a:solidFill><a:srgbClr val="{color_hex}"/></a:solidFill>'
        f'<a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:rPr>'
    )


def add_footer_text(container, color):
    sp = etree.fromstring(_textbox_xml(
        _next_sp_id(), "FooterText",
        int(Inches(0.55)), int(Inches(7.08)), int(Inches(3.0)),
        int(Inches(0.3)),
        f'<a:p><a:r>{_rpr(str(color))}'
        f"<a:t>Sample Org</a:t></a:r></a:p>"))
    container.shapes._spTree.append(sp)


def add_slide_number(master):
    sp = etree.fromstring(_textbox_xml(
        _next_sp_id(), "SlideNumber",
        int(Inches(12.35)), int(Inches(7.08)), int(Inches(0.8)),
        int(Inches(0.3)),
        '<a:p><a:pPr algn="r"/>'
        '<a:fld id="{B6F15528-9517-4E2F-8F3A-000000000001}" type="slidenum">'
        f'{_rpr("595F6B")}<a:t>1</a:t></a:fld></a:p>'))
    master.shapes._spTree.append(sp)


def _set_ph_geom(layout, idx, x=None, y=None, w=None, h=None):
    for ph in layout.placeholders:
        if ph.placeholder_format.idx == idx:
            base = {}
            for mph in layout.slide_master.placeholders:
                if mph.placeholder_format.idx == idx:
                    base = {"x": mph.left, "y": mph.top,
                            "w": mph.width, "h": mph.height}
            vals = {"x": x, "y": y, "w": w, "h": h}
            merged = {k: (v if v is not None else base.get(k))
                      for k, v in vals.items()}
            if all(v is not None for v in merged.values()):
                ph.left, ph.top = merged["x"], merged["y"]
                ph.width, ph.height = merged["w"], merged["h"]
            else:
                for key, attr in (("x", "left"), ("y", "top"),
                                  ("w", "width"), ("h", "height")):
                    if vals[key] is not None:
                        setattr(ph, attr, vals[key])
            return
    raise RuntimeError(f"layout {layout.name}: ph idx {idx} not found")


def _layout_ph_style(layout, idx, sz=None, algn=None, bold=None, color=None):
    for ph in layout.placeholders:
        if ph.placeholder_format.idx == idx:
            tx = ph._element.find(qn("p:txBody"))
            lst = tx.find(qn("a:lstStyle"))
            if lst is None:
                lst = etree.SubElement(tx, qn("a:lstStyle"))
            lp = lst.find(qn("a:lvl1pPr"))
            if lp is None:
                lp = etree.SubElement(lst, qn("a:lvl1pPr"))
            if algn:
                lp.set("algn", algn)
            if sz:
                dr = lp.find(qn("a:defRPr"))
                if dr is None:
                    dr = etree.SubElement(lp, qn("a:defRPr"))
                dr.set("sz", str(sz))
            if bold is not None or color is not None:
                dr = lp.find(qn("a:defRPr"))
                if dr is None:
                    dr = etree.SubElement(lp, qn("a:defRPr"))
                if bold is not None:
                    dr.set("b", "1" if bold else "0")
                if color is not None:
                    for fill in dr.findall(qn("a:solidFill")):
                        dr.remove(fill)
                    solid = etree.SubElement(dr, qn("a:solidFill"))
                    scheme = etree.SubElement(solid, qn("a:schemeClr"))
                    scheme.set("val", color)
            return
    raise RuntimeError(f"layout {layout.name}: ph idx {idx} not found")


def _set_ph_anchor(layout, idx, anchor):
    for ph in layout.placeholders:
        if ph.placeholder_format.idx == idx:
            tx = ph._element.find(qn("p:txBody"))
            body = tx.find(qn("a:bodyPr"))
            body.set("anchor", anchor)
            return
    raise RuntimeError(f"layout {layout.name}: ph idx {idx} not found")


def set_master_title_size(master, sz):
    txstyles = master.element.find(qn("p:txStyles"))
    st = txstyles.find(qn("p:titleStyle"))
    lp = st.find(qn("a:lvl1pPr"))
    lp.set("algn", "l")
    dr = lp.find(qn("a:defRPr"))
    dr.set("sz", str(sz))
    dr.set("b", "1")
    for f in dr.findall(qn("a:solidFill")):
        dr.remove(f)
    fill = etree.Element(qn("a:solidFill"))
    clr = etree.SubElement(fill, qn("a:schemeClr"))
    clr.set("val", "accent1")
    dr.insert(0, fill)
    body = txstyles.find(qn("p:bodyStyle"))
    for lvl, bsz in ((1, 2000), (2, 1600)):
        lp = body.find(qn(f"a:lvl{lvl}pPr"))
        dr = lp.find(qn("a:defRPr"))
        dr.set("sz", str(bsz))


def find_layout(prs, name):
    for layout in prs.slide_layouts:
        if layout.name == name:
            return layout
    raise RuntimeError(f"layout not found: {name}")


def _cell_bottom_border(cell, hexv="C8CDD6", w=9525):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("a:lnB")):
        tcPr.remove(old)
    ln_b = etree.fromstring(
        f'<a:lnB xmlns:a="{A}" w="{w}" cap="flat">'
        f'<a:solidFill><a:srgbClr val="{hexv}"/></a:solidFill></a:lnB>')
    tcPr.insert(0, ln_b)


def mark_region(slide, name, x, y, w, h):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shp.name = name
    shp.fill.background()
    shp.line.color.rgb = LIGHT_LINE
    shp.line.width = Pt(1)
    ln = shp.line._get_or_add_ln()
    dash = etree.SubElement(ln, qn("a:prstDash"))
    dash.set("val", "dash")
    return shp


def build_template():
    prs = Presentation()
    prs.slide_width = Emu(12192000)
    prs.slide_height = Emu(6858000)
    edit_theme(prs)
    master = prs.slide_masters[0]

    add_footer_text(master, GRAY_TEXT)
    add_slide_number(master)

    set_master_title_size(master, 2400)
    title_layout = find_layout(prs, "Title Slide")
    section_layout = find_layout(prs, "Section Header")
    for layout in (title_layout, section_layout):
        layout_bg(layout, "accent1")
        white_placeholder_text(layout)
        layout.element.set("showMasterSp", "0")
        add_footer_text(layout, RGBColor(0xC9, 0xD4, 0xE4))
    _layout_ph_style(title_layout, 0, sz=4000, algn="ctr")
    _layout_ph_style(title_layout, 1, sz=1600)
    _set_ph_geom(section_layout, 0, x=Inches(0.9), y=Inches(3.0),
                 w=Inches(11.5), h=Inches(1.5))
    _layout_ph_style(section_layout, 0, sz=3200)

    _widen_content_layouts(
        prs, ("Title and Content", "Two Content", "Title Only"))

    blank = find_layout(prs, "Blank")

    # --- slide 1: cover sample (layout mode reference) ---
    s = prs.slides.add_slide(title_layout)
    s.placeholders[0].text_frame.paragraphs[0].add_run().text = (
        "〇〇プロジェクト計画書（サンプル）")
    s.placeholders[1].text_frame.paragraphs[0].add_run().text = (
        "サンプル資料：ここに副題・組織名・日付")
    set_notes(s, "このスライドは表紙の見本。Title Slide レイアウトの "
                 "プレースホルダ idx0=タイトル、idx1=サブタイトルを使う。")

    # --- slide 2: TOC sample ---
    s = prs.slides.add_slide(blank)
    add_text(s, "Title", Inches(0.5), Inches(0.3), Inches(12.33), Inches(1.15),
             [("目次（サンプル）", 24, True, NAVY)])
    add_text(s, "TocBody", Inches(1.0), Inches(1.6), Inches(11), Inches(5.0),
             [("背景と目的（サンプル項目）", 20, False, INK),
              ("方針（サンプル項目）", 20, False, INK),
              ("体制とスケジュール（サンプル項目）", 20, False, INK),
              ("リスク（サンプル項目）", 20, False, INK)],
             bullet="num", spacing=12)
    set_notes(s, "このスライドは目次コンポーネントの見本。Title=見出し、"
                 "TocBody=箇条書き（1項目1段落）。")

    # --- slide 3: table sample ---
    s = prs.slides.add_slide(blank)
    add_text(s, "Title", Inches(0.5), Inches(0.3), Inches(12.33), Inches(1.15),
             [("表のサンプル：〇〇の比較", 24, True, NAVY)])
    gf = s.shapes.add_table(3, 3, Inches(0.8), Inches(1.6),
                            Inches(11.7), Inches(2.4))
    gf.name = "DataTable"
    table = gf.table
    headers = ["項目（サンプル）", "現行", "移行後"]
    body = [("項目A", "〇〇", "△△"), ("項目B", "××", "□□")]
    for c, text in enumerate(headers):
        cell = table.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        _cell_bottom_border(cell)
        run = cell.text_frame.paragraphs[0].add_run()
        run.text = text
        set_run_fonts(run, size=14, bold=True, color=WHITE)
    for r, row in enumerate(body, start=1):
        for c, text in enumerate(row):
            cell = table.cell(r, c)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if r % 2 == 1 else BAND
            _cell_bottom_border(cell)
            run = cell.text_frame.paragraphs[0].add_run()
            run.text = text
            set_run_fonts(run, size=13, color=INK)
    set_notes(s, "このスライドは表コンポーネントの見本。列数は内容に合わせて"
                 "変えてよい。行数・列数は DataTable の行・列の複製で増減する。")

    # --- slide 4: orgchart sample ---
    s = prs.slides.add_slide(blank)
    add_text(s, "Title", Inches(0.5), Inches(0.3), Inches(12.33), Inches(1.15),
             [("組織図のサンプル：〇〇体制", 24, True, NAVY)])
    mark_region(s, "OrgRegion", Inches(0.8), Inches(1.5),
                Inches(11.7), Inches(5.2))
    node = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              Inches(5.3), Inches(2.2),
                              Inches(2.6), Inches(1.0))
    node.name = "OrgNode"
    node.fill.solid()
    node.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    node.line.color.rgb = NAVY
    node.line.width = Pt(1.5)
    tf = node.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p1, p2 = tf.paragraphs[0], tf.add_paragraph()
    for p in (p1, p2):
        p.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = "部門名（サンプル）"
    set_run_fonts(r1, size=14, bold=True, color=NAVY)
    r2 = p2.add_run()
    r2.text = "役割・担当"
    set_run_fonts(r2, size=11, color=GRAY_TEXT)
    set_notes(s, "このスライドは組織図コンポーネントの見本。OrgRegion が描画"
                 "範囲、OrgNode が箱の雛形。階層は最大3段。")

    # --- slide 5: timeline sample ---
    s = prs.slides.add_slide(blank)
    add_text(s, "Title", Inches(0.5), Inches(0.3), Inches(12.33), Inches(1.15),
             [("スケジュールのサンプル：〇〇計画", 24, True, NAVY)])
    mark_region(s, "TimelineRegion", Inches(0.8), Inches(2.75),
                Inches(11.7), Inches(2.9))
    step = s.shapes.add_shape(MSO_SHAPE.PENTAGON,
                              Inches(1.0), Inches(3.0),
                              Inches(3.2), Inches(2.4))
    step.name = "TimelineStep"
    step.adjustments[0] = 0.15
    step.fill.solid()
    step.fill.fore_color.rgb = NAVY
    step.line.color.rgb = NAVY
    tf = step.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.05)
    tf.margin_right = Inches(0.05)
    p1 = tf.paragraphs[0]
    p2, p3 = tf.add_paragraph(), tf.add_paragraph()
    for p in (p1, p2, p3):
        p.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = "工程名（サンプル）"
    set_run_fonts(r1, size=16, bold=True, color=WHITE)
    r2 = p2.add_run()
    r2.text = "時期"
    set_run_fonts(r2, size=13, color=WHITE)
    r3 = p3.add_run()
    r3.text = "作業内容"
    set_run_fonts(r3, size=12, color=RGBColor(0xDC, 0xE3, 0xEE))
    set_notes(s, "このスライドはタイムラインコンポーネントの見本。"
                 "TimelineRegion が描画範囲、TimelineStep が1工程の雛形。")

    # --- slide 6: two-column sample ---
    s = prs.slides.add_slide(blank)
    add_text(s, "Title", Inches(0.5), Inches(0.3), Inches(12.33), Inches(1.15),
             [("2段比較のサンプル：現行と移行後", 24, True, NAVY)])
    add_text(s, "LeftHeading", Inches(0.8), Inches(1.5),
             Inches(5.6), Inches(0.55),
             [("現行（サンプル）", 18, True, NAVY)])
    add_text(s, "LeftBody", Inches(0.8), Inches(2.15),
             Inches(5.6), Inches(4.4),
             [("項目A 〇〇", 16, False, INK),
              ("項目B △△", 16, False, INK)],
             bullet="char", spacing=6)
    add_text(s, "RightHeading", Inches(6.9), Inches(1.5),
             Inches(5.6), Inches(0.55),
             [("移行後（サンプル）", 18, True, ACCENT)])
    add_text(s, "RightBody", Inches(6.9), Inches(2.15),
             Inches(5.6), Inches(4.4),
             [("項目A ××", 16, False, INK),
              ("項目B □□", 16, False, INK)],
             bullet="char", spacing=6)
    set_notes(s, "このスライドは2段比較コンポーネントの見本。"
                 "Left/RightHeading=列見出し、Left/RightBody=列の箇条書き。")

    # --- slide 7: closing sample ---
    s = prs.slides.add_slide(blank)
    add_text(s, "Title", Inches(0.5), Inches(0.3), Inches(12.33), Inches(1.15),
             [("まとめ（サンプル）：〇〇のお願い", 24, True, NAVY)])
    add_text(s, "ClosingBody", Inches(1.0), Inches(1.8),
             Inches(11), Inches(4.5),
             [("ご承認いただきたい事項1（サンプル）", 20, False, INK),
              ("ご承認いただきたい事項2（サンプル）", 20, False, INK),
              ("ご承認いただきたい事項3（サンプル）", 20, False, INK)],
             bullet="char", spacing=10)
    set_notes(s, "このスライドはクロージングコンポーネントの見本。"
                 "ClosingBody=箇条書き（1項目1段落）。")

    # --- slide 8: chart sample ---
    s = prs.slides.add_slide(blank)
    add_text(s, "Title", Inches(0.5), Inches(0.3), Inches(12.33), Inches(1.15),
             [("グラフのサンプル：〇〇の推移", 24, True, NAVY)])
    cd = CategoryChartData()
    cd.categories = ["Q1", "Q2", "Q3", "Q4"]
    cd.add_series("計画（サンプル）", (40, 55, 62, 71))
    cd.add_series("実績（サンプル）", (35, 48, 66, 68))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,
                            Inches(0.8), Inches(1.7),
                            Inches(11.7), Inches(5.0), cd)
    gf.name = "DataChart"
    chart = gf.chart
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    set_notes(s, "このスライドはグラフコンポーネントの見本。DataChart の "
                 "データだけ差し替える。グラフの種類（縦棒）と配色は"
                 "テンプレのまま使う。")

    return prs


def edit_minimal_theme(prs):
    theme_part = next(
        (rel.target_part for rel in prs.slide_masters[0].part.rels.values()
         if rel.reltype.endswith("/theme")), None)
    if theme_part is None:
        raise RuntimeError("theme part not found")
    root = etree.fromstring(theme_part.blob)
    ns = {"a": A}
    colors = {
        "dk1": "202124", "lt1": "FFFFFF", "dk2": "0F5B4F",
        "lt2": "EEF4F2", "accent1": "0F5B4F", "accent2": "E07A1F",
        "accent3": "6C817B", "accent4": "9DAEA9", "accent5": "CAD4D1",
        "accent6": "718782", "hlink": "E07A1F", "folHlink": "8F5522",
    }
    for name, value in colors.items():
        slot = root.find(f".//a:clrScheme/a:{name}", ns)
        for child in list(slot):
            slot.remove(child)
        color = etree.SubElement(slot, qn("a:srgbClr"))
        color.set("val", value)
    for tag in ("a:majorFont", "a:minorFont"):
        group = root.find(f".//a:fontScheme/{tag}", ns)
        for name in ("latin", "ea"):
            font = group.find(f"a:{name}", ns)
            if font is None:
                font = etree.SubElement(group, qn(f"a:{name}"))
            font.set("typeface", FONT)
    if hasattr(theme_part, "element"):
        theme_part._element = root
    else:
        theme_part._blob = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=True)


def build_minimal_template():
    prs = Presentation()
    prs.slide_width = Emu(12192000)
    prs.slide_height = Emu(6858000)
    edit_minimal_theme(prs)
    _widen_content_layouts(prs, ("Title and Content", "Title Only"))
    _style_minimal_titles(prs)
    title_slide = prs.slides.add_slide(find_layout(prs, "Title Slide"))
    title_slide.placeholders[0].text = "社内問い合わせ窓口の一本化"
    title_slide.placeholders[1].text = "Sample Org"

    content_layout = find_layout(prs, "Title and Content")
    table_slide = prs.slides.add_slide(content_layout)
    table_slide.placeholders[0].text = "サンプル表"
    table_shape = table_slide.shapes.add_table(
        4, 3, Inches(0.9), Inches(1.7), Inches(11.5), Inches(3.2))
    table_shape.name = "DataTable"
    for row, values in enumerate((
            ("項目", "現状", "目標"),
            ("受付", "複数窓口", "一本化"),
            ("回答", "担当者ごと", "共通FAQ"),
            ("記録", "分散", "一元管理"))):
        for col, value in enumerate(values):
            cell = table_shape.table.cell(row, col)
            cell.text = value
            cell.margin_left = Inches(0.12)
            cell.margin_right = Inches(0.12)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.04)

    org_slide = prs.slides.add_slide(content_layout)
    org_slide.placeholders[0].text = "サンプル体制図"
    mark_region(org_slide, "OrgRegion", Inches(0.9), Inches(1.7),
                Inches(11.5), Inches(4.8))
    node = org_slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(5.3), Inches(2.4),
        Inches(2.6), Inches(1.0))
    node.name = "OrgNode"
    node.fill.solid()
    node.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    node.line.color.rgb = RGBColor(0x0F, 0x5B, 0x4F)
    node.text_frame.text = "責任者\n氏名"
    for paragraph in node.text_frame.paragraphs:
        paragraph.alignment = PP_ALIGN.CENTER
        for run in paragraph.runs:
            set_run_fonts(run, size=14, color=RGBColor(0x20, 0x21, 0x24))
    return prs


def _style_minimal_titles(prs):
    for name in ("Title Slide", "Section Header", "Title Only",
                 "Title and Content"):
        layout = find_layout(prs, name)
        _set_ph_geom(layout, 0, x=Inches(0.5), y=Inches(0.4),
                     w=Inches(12.33), h=Inches(1.15))
        _set_ph_anchor(layout, 0, "t")
        _layout_ph_style(layout, 0, sz=2800, algn="l", bold=True,
                         color="dk2")


def _widen_content_layouts(prs, names):
    for lname in names:
        layout = find_layout(prs, lname)
        _set_ph_geom(layout, 0, x=Inches(0.5), y=Inches(0.3),
                     w=Inches(12.33), h=Inches(1.15))
        _set_ph_anchor(layout, 0, "t")
    if "Title and Content" in names:
        content = find_layout(prs, "Title and Content")
        _set_ph_geom(content, 1, x=Inches(0.5), w=Inches(12.33))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=("sample", "minimal"),
                    default="sample")
    ap.add_argument("-o", "--output",
                    default=str(Path(__file__).resolve().parents[1]
                                / "templates" / "sample-org" / "template.pptx"))
    args = ap.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs = (build_minimal_template() if args.variant == "minimal"
           else build_template())
    prs.save(str(out))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
