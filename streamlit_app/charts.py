"""Turns the backend's ChartSpec + rows into a Plotly figure — one spec, one renderer, the same
shape the real frontend will eventually draw from (backend app/agents/visualizer/charts.py:ChartSpec:
type, x, y, series, title). The backend never produces both multiple y columns and a series split at
once (visualizer/charts.py only splits by series when there's exactly one measure), so there's no
conflict between the two below.
"""

import pandas as pd
import plotly.express as px

_PLOTTERS = {
    "bar": px.bar,
    "line": px.line,
    "area": px.area,
    "scatter": px.scatter,
}


def figure(chart: dict, rows: list[dict]):
    df = pd.DataFrame(rows)
    title = chart.get("title")

    if chart["type"] == "pie":
        return px.pie(df, names=chart["x"], values=chart["y"][0], title=title)

    plot = _PLOTTERS[chart["type"]]
    kwargs = {"x": chart["x"], "y": chart["y"], "title": title}
    if chart.get("series"):
        kwargs["color"] = chart["series"]
    return plot(df, **kwargs)
