#!/usr/bin/env python3
"""Inventory a .pptx template: slide size, layouts, placeholders, slides,
shapes, tables, speaker notes. Optionally render slide thumbnails.

Usage: inventory.py TEMPLATE.pptx [--json OUT] [--thumbs DIR]
"""
import argparse
from collections import Counter
import json
import sys
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn

from engine import render_pngs

EMU_PER_IN = 914400


def _in(v):
    return round(v / EMU_PER_IN, 3) if v is not None else None


def bbox(shape):
    return [_in(shape.left), _in(shape.top), _in(shape.width),
            _in(shape.height)]


GRAPHIC_URIS = {
    "http://schemas.openxmlformats.org/drawingml/2006/chart": "chart",
    "http://schemas.openxmlformats.org/drawingml/2006/diagram": "smartart",
    "http://schemas.openxmlformats.org/drawingml/2006/table": "table",
}


def _graphic_kind(shape):
    """Kind of a graphicFrame's content ('chart'/'smartart'/'table')."""
    el = shape._element
    if el.tag != qn("p:graphicFrame"):
        return None
    gd = el.find(f"{qn('a:graphic')}/{qn('a:graphicData')}")
    if gd is None:
        return None
    return GRAPHIC_URIS.get(gd.get("uri"), gd.get("uri"))


def _shape_info(shape):
    info = {"name": shape.name, "type": str(shape.shape_type),
            "bbox": bbox(shape)}
    if shape.is_placeholder:
        info["placeholder_idx"] = shape.placeholder_format.idx
    if shape.shape_type == 6:  # group
        info["children"] = [_shape_info(s) for s in shape.shapes]
        return info
    if shape.has_text_frame:
        text = shape.text_frame.text.strip()
        if text:
            info["text"] = text[:80]
    kind = _graphic_kind(shape)
    if kind:
        info["graphic"] = kind
    if getattr(shape, "has_table", False) and shape.has_table:
        info["table"] = {"rows": len(shape.table.rows),
                         "cols": len(shape.table.columns)}
    return info


def _theme_data(prs):
    master = prs.slide_masters[0]
    theme_part = next(
        (rel.target_part for rel in master.part.rels.values()
         if rel.reltype.endswith("/theme")), None)
    if theme_part is None:
        return {"colors": {}, "fonts": {}}
    root = etree.fromstring(theme_part.blob)
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    keys = ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3",
            "accent4", "accent5", "accent6", "hlink", "folHlink")
    color_scheme = root.find(".//a:themeElements/a:clrScheme", ns)
    colors = {}
    if color_scheme is not None:
        for key in keys:
            slot = color_scheme.find(f"a:{key}", ns)
            if slot is not None and len(slot):
                color = slot[0]
                value = color.get("val") or color.get("lastClr")
                if value:
                    colors[key] = f"#{value.upper()}"
    font_scheme = root.find(".//a:fontScheme", ns)
    fonts = {}
    if font_scheme is not None:
        for name, tag in (("major", "majorFont"), ("minor", "minorFont")):
            group = font_scheme.find(f"a:{tag}", ns)
            fonts[name] = {
                key: (group.find(f"a:{key}", ns).get("typeface", "")
                      if group is not None and group.find(f"a:{key}", ns)
                      is not None else "")
                for key in ("latin", "ea")
            }
    return {"colors": colors, "fonts": fonts}


def _profile(prs):
    used = Counter()
    parts = [slide.part for slide in prs.slides]
    parts.extend(layout.part for layout in prs.slide_layouts)
    for part in parts:
        root = etree.fromstring(part.blob)
        for color in root.iter(qn("a:srgbClr")):
            value = color.get("val")
            if value:
                used[f"#{value.upper()}"] += 1
    ignored = {"TITLE (1)", "CENTER_TITLE (3)", "DATE (16)",
               "FOOTER (15)", "SLIDE_NUMBER (13)", "HEADER (14)"}
    candidates = [
        layout.name for layout in prs.slide_layouts
        if all(str(ph.placeholder_format.type) in ignored
               for ph in layout.placeholders)
    ]
    return {
        "theme": _theme_data(prs),
        "used_colors": [{"rgb": color, "count": count}
                        for color, count in used.most_common(8)],
        "canvas_candidates": candidates,
    }


def collect(template_path):
    prs = Presentation(str(template_path))
    data = {
        "file": str(template_path),
        "slide_size": [_in(prs.slide_width), _in(prs.slide_height)],
        "layouts": [],
        "slides": [],
    }
    for i, layout in enumerate(prs.slide_layouts):
        phs = []
        for ph in layout.placeholders:
            phs.append({
                "idx": ph.placeholder_format.idx,
                "type": str(ph.placeholder_format.type),
                "name": ph.name,
                "bbox": bbox(ph),
            })
        data["layouts"].append({"index": i, "name": layout.name,
                                "placeholders": phs})
    for i, slide in enumerate(prs.slides, start=1):
        entry = {"index": i, "layout": slide.slide_layout.name,
                 "shapes": [_shape_info(sh) for sh in slide.shapes]}
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                entry["notes"] = notes
        data["slides"].append(entry)
    data.update(_profile(prs))
    return data


def print_report(data):
    print(f"template : {data['file']}")
    print(f"size     : {data['slide_size'][0]} x {data['slide_size'][1]} in")
    print(f"theme    : {data['theme']['colors']}")
    print(f"fonts    : {data['theme']['fonts']}")
    print(f"used RGB : {data['used_colors']}")
    print(f"canvas   : {data['canvas_candidates']}")
    print("\n== slide layouts ==")
    for layout in data["layouts"]:
        print(f"[{layout['index']}] {layout['name']}")
        for ph in layout["placeholders"]:
            print(f"    ph idx={ph['idx']} type={ph['type']} "
                  f"name={ph['name']!r} bbox={ph['bbox']}")
    print("\n== slides ==")
    for slide in data["slides"]:
        print(f"slide {slide['index']} (layout: {slide['layout']})")
        for sh in slide["shapes"]:
            _print_shape(sh, "    ")
        if "notes" in slide:
            print(f"    notes: {slide['notes']}")


def _print_shape(sh, indent):
    extra = ""
    if "placeholder_idx" in sh:
        extra += f" ph_idx={sh['placeholder_idx']}"
    if "graphic" in sh:
        extra += f" graphic={sh['graphic']}"
    if "table" in sh:
        extra += f" table={sh['table']['rows']}x{sh['table']['cols']}"
    text = f" text={sh['text']!r}" if "text" in sh else ""
    print(f"{indent}{sh['name']!r} {sh['type']} bbox={sh['bbox']}"
          f"{extra}{text}")
    for child in sh.get("children", []):
        _print_shape(child, indent + "  ")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("template")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--thumbs", dest="thumbs_dir")
    ap.add_argument("--engine", default="auto",
                    choices=("auto", "powerpoint", "libreoffice"))
    args = ap.parse_args(argv)

    data = collect(Path(args.template))
    print_report(data)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")
    if args.thumbs_dir:
        paths = render_pngs(args.template, args.thumbs_dir, args.engine)
        print(f"\nwrote {len(paths)} thumbnails to {args.thumbs_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
