import unicodedata

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from lxml import etree
from pptx.oxml.ns import qn

CHART_TYPES = {
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "line": XL_CHART_TYPE.LINE,
    "pie": XL_CHART_TYPE.PIE,
    "stacked_column": XL_CHART_TYPE.COLUMN_STACKED,
    "stacked_bar": XL_CHART_TYPE.BAR_STACKED,
}
FALLBACK_MARK = "pptx-deck-fallback"
GENERATED_MARK = "pptx-deck-generated"
LINE_HEIGHT = 1.2
THEME_KEYS = ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3",
              "accent4", "accent5", "accent6", "hlink", "folHlink")


class BuildError(Exception):
    pass


def fail(message):
    raise BuildError(message)


def mark_el(el, mark):
    for child in el:
        for c in child.iter(qn("p:cNvPr")):
            c.set("descr", mark)
            return


def read_theme(prs):
    master = prs.slide_masters[0]
    theme_part = next(
        (rel.target_part for rel in master.part.rels.values()
         if rel.reltype.endswith("/theme")), None)
    if theme_part is None:
        return {"colors": {}, "fonts": {"major": {}, "minor": {}}}
    root = etree.fromstring(theme_part.blob)
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    color_scheme = root.find(".//a:themeElements/a:clrScheme", ns)
    colors = {}
    if color_scheme is not None:
        for key in THEME_KEYS:
            slot = color_scheme.find(f"a:{key}", ns)
            if slot is not None and len(slot):
                color = slot[0]
                value = color.get("val") or color.get("lastClr")
                if value:
                    colors[key] = f"#{value.upper()}"
    font_scheme = root.find(".//a:fontScheme", ns)
    fonts = {}
    for name, tag in (("major", "majorFont"), ("minor", "minorFont")):
        group = font_scheme.find(f"a:{tag}", ns) if font_scheme is not None \
            else None
        fonts[name] = {
            key: (group.find(f"a:{key}", ns).get("typeface", "")
                  if group is not None and group.find(f"a:{key}", ns)
                  is not None else "")
            for key in ("latin", "ea")
        }
    return {"colors": colors, "fonts": fonts}


def char_units(ch):
    return 1.0 if unicodedata.east_asian_width(ch) in ("F", "W") else 0.55


def chart_data(value):
    data = CategoryChartData()
    data.categories = value["categories"]
    for series in value["series"]:
        if value.get("number_format"):
            data.add_series(series["name"], series["values"],
                            number_format=value["number_format"])
        else:
            data.add_series(series["name"], series["values"])
    return data


def finish_chart(chart, value):
    try:
        plot = chart.plots[0]
        plot.has_data_labels = True
        if value.get("number_format"):
            plot.data_labels.number_format = value["number_format"]
            plot.data_labels.number_format_is_linked = False
    except Exception:
        pass
    chart.has_legend = len(value["series"]) > 1
