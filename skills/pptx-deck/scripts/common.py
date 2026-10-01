import math
import unicodedata

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
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


class BuildError(Exception):
    pass


def fail(message):
    raise BuildError(message)


def mark_el(el, mark):
    for child in el:
        for c in child.iter(qn("p:cNvPr")):
            c.set("descr", mark)
            return


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
