'''
Created on 5 Oct 2025

@author: T-RexPO
'''
import dash
from dash import dcc, html
from dash.dependencies import Output, Input, State
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
import sqlalchemy
import webbrowser
from threading import Timer
import base64
import os

# ---- Regional centres with lat/lon -------------------------------------------
regions = [
    {"region": "Glasgow", "lat": 55.8642, "lon": -4.2518},
    {"region": "Edinburgh", "lat": 55.9533, "lon": -3.1883},
    {"region": "Newcastle", "lat": 54.9784, "lon": -1.6174},
    {"region": "Liverpool", "lat": 53.4084, "lon": -2.9916},
    {"region": "Manchester", "lat": 53.4808, "lon": -2.2426},
    {"region": "Birmingham", "lat": 52.4862, "lon": -1.8904},
    {"region": "London", "lat": 51.5074, "lon": -0.1278},
]

data = pd.DataFrame(regions)
data["incidents"] = [120, 95, 80, 110, 150, 130, 200]
data["changes"] = [45, 60, 35, 50, 70, 55, 100]
data["problems"] = [15, 20, 10, 25, 30, 22, 40]
data["resolution_time"] = [240, 180, 200, 260, 300, 280, 350]  # minutes
data.to_csv("uk_services.csv", index=False)

# ---- Initialize Time Series Data --------------------------------------------
df_trend = pd.DataFrame(columns=["date", "region", "resolution_time"])

# ---- Dash App ----------------------------------------------------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

# ---- Colour map for regions (used across map, trend, and region-coloured bars)
region_colors = {
    "Glasgow": "red",
    "Edinburgh": "blue",
    "Newcastle": "green",
    "Liverpool": "orange",
    "Manchester": "purple",
    "Birmingham": "brown",
    "London": "black",
}

# ---- KPI Card Component ------------------------------------------------------
def kpi_card(title, value, color):
    return dbc.Card(
        dbc.CardBody([
            html.H4(title, className="card-title", style={"textAlign": "center", "color": "white"}),
            html.H2(value, className="card-text", style={"textAlign": "center", "color": "white"}),
        ]),
        style={
            "margin": "10px",
            "boxShadow": "0px 0px 8px rgba(0,0,0,0.1)",
            "backgroundColor": color,
            "borderRadius": "10px"
        }
    )

# ---- Layout ------------------------------------------------------------------
app.layout = html.Div([
    dbc.Row([
        dbc.Col(html.H1("Service Management Dashboard",
                        style={'textAlign': 'center', "marginBottom": "20px"}), width=12)
    ]),

    # Hidden stores for file path and mysql connection
    dcc.Store(id="csv-path", data="uk_services.csv"),
    dcc.Store(id="mysql-conn", data={"host": "localhost", "user": "root", "password": "", "database": ""}),

    # KPI Row
    dbc.Row(id="kpi-cards", justify="center"),

    # ---- Dropdown Controls for map + bar ----
    dbc.Row([
        dbc.Col([
            html.Label("Select Area Centre:"),
            dcc.Dropdown(
                id="region-select",
                options=[{"label": "All", "value": "All"}] +
                        [{"label": r, "value": r} for r in data["region"].unique()],
                value="All",
                clearable=False,
                style={"width": "90%"}
            )
        ], width=3),

        dbc.Col([
            html.Label("Select Dashboard View:"),
            dcc.Dropdown(
                id="view-toggle",
                options=[
                    {"label": "None", "value": "none"},
                    {"label": "Incidents – Counts", "value": "incidents-counts"},
                    {"label": "Incidents – Percentages", "value": "incidents-percent"},
                    {"label": "Changes – Counts", "value": "changes-counts"},
                    {"label": "Changes – Percentages", "value": "changes-percent"},
                    {"label": "Problems – Counts", "value": "problems-counts"},
                    {"label": "Problems – Percentages", "value": "problems-percent"},
                ],
                value="none",
                clearable=False,
                style={"width": "90%"}
            )
        ], width=3),

        dbc.Col([
            html.Label("Select Data Source:"),
            dcc.Dropdown(
                id="data-source",
                options=[
                    {"label": "Simulator", "value": "simulator"},
                    {"label": "CSV", "value": "csv"},
                    {"label": "MySQL Database", "value": "mysql"},
                ],
                value="simulator",
                clearable=False,
                style={"width": "90%"}
            )
        ], width=3),
    ], style={"marginBottom": "20px", "justifyContent": "center"}),

    # ---- Pop-up Modals ----
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("CSV File Selection")),
        dbc.ModalBody([
            dbc.Label("Upload CSV file:"),
            dcc.Upload(
                id="csv-upload",
                children=html.Div(["Drag and Drop or ", html.A("Select File")]),
                style={
                    "width": "100%",
                    "height": "60px",
                    "lineHeight": "60px",
                    "borderWidth": "1px",
                    "borderStyle": "dashed",
                    "borderRadius": "5px",
                    "textAlign": "center",
                    "marginBottom": "10px"
                },
                multiple=False
            ),
            html.Div(id="csv-uploaded-file", style={"fontSize": "12px", "color": "green"})
        ]),
        dbc.ModalFooter(
            dbc.Button("OK", id="csv-ok", className="ms-auto", n_clicks=0)
        ),
    ], id="csv-modal", is_open=False),

    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("MySQL Connection Details")),
        dbc.ModalBody([
            dbc.Label("Host:"), dbc.Input(id="mysql-host", type="text", value="localhost"),
            dbc.Label("User:"), dbc.Input(id="mysql-user", type="text", value="root"),
            dbc.Label("Password:"), dbc.Input(id="mysql-pass", type="password", value=""),
            dbc.Label("Database:"), dbc.Input(id="mysql-db", type="text", value=""),
        ]),
        dbc.ModalFooter(
            dbc.Button("OK", id="mysql-ok", className="ms-auto", n_clicks=0)
        ),
    ], id="mysql-modal", is_open=False),

    # ---- Map + Bar ----
    dbc.Row([
        dbc.Col(dcc.Graph(id="uk-map"), width=6),
        dbc.Col(dcc.Graph(id="uk-bar"), width=6),
    ]),

    # ---- Modal for bar details (click pop-up list) ----
    dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle(id="bar-modal-title")),
        dbc.ModalBody(
            html.Div(
                id="bar-modal-list",
                style={
                    "maxHeight": "70vh",
                    "overflowY": "auto",
                    "paddingRight": "10px",
                    "scrollbarWidth": "thin",
                    "scrollbarColor": "#888 #f1f1f1"
                }
            )
        ),
        dbc.ModalFooter(
            dbc.Button("Close", id="bar-modal-close", className="ms-auto", n_clicks=0)
        ),
    ],
    id="bar-modal",
    is_open=False,
    size="lg",
    scrollable=False,   # ✅ disable modal scroll to prevent double scrollbar
    backdrop=True,
    keyboard=True,
),


    # ---- Live Controls + Trend Chart ----
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Span("● ", id="live-dot",
                          style={"color": "grey", "fontSize": "20px"}),  # default paused
                html.Span("PAUSED", id="live-label",
                          style={"color": "grey", "fontWeight": "bold",
                                 "fontSize": "16px", "marginRight": "20px"}),

                html.Button("Start/Refresh", id="start-btn", n_clicks=0,
                            style={"margin": "0px 10px", "width": "150px"}),
                html.Button("Resume", id="pause-btn", n_clicks=0,
                            style={"marginRight": "10px", "width": "150px"}),

                dcc.Dropdown(
                    id="trend-region-select",
                    options=[{"label": "All", "value": "All"}] +
                            [{"label": r, "value": r} for r in data["region"].unique()],
                    value="All",
                    clearable=False,
                    style={"width": "200px", "marginLeft": "20px"}
                )
            ], style={"marginBottom": "10px", "display": "flex", "justifyContent": "center", "alignItems": "center"}),

            html.Div([
                dcc.Graph(id="uk-trend", style={"height": "600px", "width": "1200px"}),
                html.Div(id="video-container")  # container for local video (Glasgow)
            ], style={"border": "3px solid #444", "borderRadius": "8px",
                      "overflow": "scroll", "height": "500px", "width": "1000px",
                      "margin": "0 auto"})
        ], width=12)
    ], style={"marginTop": "30px"}),

    dcc.Interval(id="interval-component", interval=2000, n_intervals=0, disabled=True)
])

# ---- CSV Upload Logic --------------------------------------------------------
@app.callback(
    Output("csv-modal", "is_open"),
    Input("data-source", "value"),
    Input("csv-ok", "n_clicks"),
    State("csv-modal", "is_open")
)
def toggle_csv_modal(source, ok_click, is_open):
    if source == "csv" and not is_open:
        return True
    if ok_click and ok_click > 0:
        return False
    return is_open

@app.callback(
    Output("csv-uploaded-file", "children"),
    Output("csv-path", "data"),
    Input("csv-upload", "contents"),
    State("csv-upload", "filename"),
    prevent_initial_call=True
)
def handle_csv_upload(contents, filename):
    if contents is None:
        return "", "uk_services.csv"
    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)
    save_path = os.path.join(os.getcwd(), filename)
    with open(save_path, "wb") as f:
        f.write(decoded)
    return f"Uploaded: {filename}", save_path

# ---- MySQL Modal Logic -------------------------------------------------------
@app.callback(
    Output("mysql-modal", "is_open"),
    Input("data-source", "value"),
    Input("mysql-ok", "n_clicks"),
    State("mysql-modal", "is_open")
)
def toggle_mysql_modal(source, ok_click, is_open):
    if source == "mysql" and not is_open:
        return True
    if ok_click and ok_click > 0:
        return False
    return is_open

@app.callback(
    Output("mysql-conn", "data"),
    Input("mysql-ok", "n_clicks"),
    State("mysql-host", "value"),
    State("mysql-user", "value"),
    State("mysql-pass", "value"),
    State("mysql-db", "value"),
    prevent_initial_call=True
)
def set_mysql_conn(ok_click, host, user, password, db):
    return {"host": host or "localhost", "user": user or "root", "password": password or "", "database": db or ""}

# ---- Start/Pause/Refresh Callback --------------------------------------------
@app.callback(
    Output("interval-component", "disabled"),
    Output("live-dot", "style"),
    Output("live-label", "children"),
    Output("live-label", "style"),
    Input("start-btn", "n_clicks"),
    Input("pause-btn", "n_clicks"),
    prevent_initial_call=True
)
def toggle_interval(start_clicks, pause_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger == "pause-btn":
        return True, {"color": "grey", "fontSize": "20px"}, \
               "PAUSED", {"color": "grey", "fontWeight": "bold", "fontSize": "16px"}
    elif trigger == "start-btn":
        return False, {"color": "red", "fontSize": "20px",
                       "animation": "blinker 1s linear infinite"}, \
               "LIVE", {"color": "red", "fontWeight": "bold", "fontSize": "16px"}
# ---- Main Update Callback ----------------------------------------------------
@app.callback(
    Output("uk-map", "figure"),
    Output("uk-bar", "figure"),
    Output("kpi-cards", "children"),
    Output("uk-trend", "figure"),
    Input("region-select", "value"),
    Input("view-toggle", "value"),
    Input("data-source", "value"),
    Input("csv-path", "data"),
    Input("mysql-conn", "data"),
    Input("trend-region-select", "value"),
    Input("interval-component", "n_intervals"),
    Input("start-btn", "n_clicks")
)
def update_graph(region_selection, view_selection, data_source, csv_path, mysql_conn,
                 trend_region, n_intervals, start_clicks):
    global df_trend, data

    # ----- Refresh KPI values when Start/Refresh clicked OR when live ticking -----
    if (n_intervals and n_intervals > 0) or (start_clicks and start_clicks > 0):
        data["incidents"] = np.random.randint(50, 250, size=len(data))
        data["changes"] = np.random.randint(20, 120, size=len(data))
        data["problems"] = np.random.randint(5, 60, size=len(data))
        data["resolution_time"] = np.random.randint(100, 400, size=len(data))

    # ---- Select Data Source ----
    if data_source == "csv":
        try:
            dff = pd.read_csv(csv_path)
        except Exception:
            dff = data.copy()
    elif data_source == "mysql":
        try:
            user = mysql_conn.get("user", "")
            pw = mysql_conn.get("password", "")
            host = mysql_conn.get("host", "localhost")
            dbname = mysql_conn.get("database", "")
            conn_str = f"mysql+pymysql://{user}:{pw}@{host}/{dbname}"
            engine = sqlalchemy.create_engine(conn_str)
            dff = pd.read_sql("SELECT * FROM services", engine)
        except Exception:
            dff = data.copy()
    else:
        dff = data.copy()

    # Ensure required columns exist if external source is used
    expected_cols = {"region", "lat", "lon", "incidents", "changes", "problems", "resolution_time"}
    if not expected_cols.issubset(set(dff.columns)):
        dff = data.copy()

    # ---- BAR CHART ----
    if view_selection == "none":
        # MODE 1: "Select Area Centre" view — show grouped bars by type (incidents/changes/problems)
        dff_mapbar = dff.copy()
        if region_selection != "All":
            dff_mapbar = dff_mapbar[dff_mapbar["region"] == region_selection]

        dff_counts = dff_mapbar.melt(
            id_vars=["region"], value_vars=["incidents", "changes", "problems"],
            var_name="type", value_name="count"
        )
        # Keep the original three-type colours for readability
        fig_bar = px.bar(
            dff_counts, x="region", y="count", color="type", text="count",
            barmode="group",
            color_discrete_map={
                "incidents": "crimson",
                "changes": "royalblue",
                "problems": "darkorange"
            },
            title="Incidents / Changes / Problems by Region"
        )
        fig_bar.update_xaxes(title="")
        fig_bar.update_yaxes(title="Count")
    else:
        # MODE 2: Other dashboard views — colour by region with consistent palette
        metric = view_selection.split("-")[0]
        dff_copy = dff.copy()
        if "percent" in view_selection:
            total = dff_copy[metric].sum()
            dff_copy["value"] = (dff_copy[metric] / total * 100).round(2) if total else 0
        else:
            dff_copy["value"] = dff_copy[metric]
        dff_sorted = dff_copy.sort_values("value", ascending=False)
        fig_bar = px.bar(
            dff_sorted,
            x="region",
            y="value",
            text=dff_sorted["value"].apply(lambda v: f"{v:.2f}" if "percent" in view_selection else str(v)),
            color="region",
            color_discrete_map=region_colors,
            title=view_selection.replace("-", " ").title()
        )
        fig_bar.update_yaxes(title="%" if "percent" in view_selection else "Count")
        fig_bar.update_xaxes(title="")

    # ---- KPI Cards ----
    kpi_cards = [
        dbc.Col(kpi_card("Total Incidents", int(dff["incidents"].sum()), "crimson"), width=3),
        dbc.Col(kpi_card("Total Changes", int(dff["changes"].sum()), "royalblue"), width=3),
        dbc.Col(kpi_card("Total Problems", int(dff["problems"].sum()), "darkorange"), width=3),
        dbc.Col(kpi_card("Avg Resolution Time (mins)", f"{round(float(dff['resolution_time'].mean()), 1)}", "purple"), width=3),
    ]

    # ---- MAP (consistent region colours) ----
    fig_map = px.scatter_mapbox(
        dff, lat="lat", lon="lon", size="incidents", color="region",
        color_discrete_map=region_colors,
        hover_name="region", hover_data=["incidents", "changes", "problems", "resolution_time"],
        size_max=40, zoom=5, mapbox_style="open-street-map",
        title="Incidents by Area Centre"
    )

    # ---- TREND (live time series) ----
    if (n_intervals and n_intervals > 0) or (start_clicks and start_clicks > 0):
        now = datetime.now().replace(microsecond=0)
        new_rows = []
        for _, row in data.iterrows():
            res = row["resolution_time"]
            new_rows.append({"date": now, "region": row["region"], "resolution_time": res})
        df_add = pd.DataFrame(new_rows)
        # keep last 100 points per region
        df_combined = pd.concat([df_trend, df_add], ignore_index=True)
        df_combined = df_combined.sort_values(["region", "date"])
        df_combined = df_combined.groupby("region").tail(100).reset_index(drop=True)
        globals()["df_trend"] = df_combined  # write back to global

    df_filtered = df_trend if trend_region == "All" else df_trend[df_trend["region"] == trend_region]
    fig_trend = go.Figure()
    for region in df_filtered["region"].unique():
        region_data = df_filtered[df_filtered["region"] == region].sort_values("date")
        color = region_colors.get(region, None)
        fig_trend.add_trace(go.Scatter(
            x=region_data["date"], y=region_data["resolution_time"],
            mode="lines+markers", name=f"{region} Resolution Time",
            line=dict(color=color), marker=dict(color=color), showlegend=True
        ))

    fig_trend.update_xaxes(tickformat="%a %d/%m/%Y %H:%M")
    fig_trend.update_yaxes(range=[0, 480], dtick=120, autorange=False)
    fig_trend.update_layout(
        title="Live Incident Resolution Time Trend (mins)",
        xaxis_title="Date/Time", yaxis_title="Resolution Time (mins)",
        template="plotly_white", showlegend=True
    )

    return fig_map, fig_bar, kpi_cards, fig_trend

# ---- Bar click -> open modal with list ---------------------------------------
@app.callback(
    Output("bar-modal", "is_open"),
    Output("bar-modal-title", "children"),
    Output("bar-modal-list", "children"),
    Input("uk-bar", "clickData"),
    Input("bar-modal-close", "n_clicks"),
    State("bar-modal", "is_open"),
    prevent_initial_call=True
)
def show_bar_details(clickData, close_clicks, is_open):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger == "bar-modal-close":
        return False, dash.no_update, dash.no_update

    if trigger == "uk-bar" and clickData is not None:
        p = clickData["points"][0]
        region = p.get("x", "Unknown")
        metric_name = "Value"
        count = int(p.get("y", 0))
        items = [html.Li(f"{metric_name} #{i+1} – {region}") for i in range(min(count, 200))]
        return True, f"{region} – {metric_name} ({count})", html.Ul(items, style={"maxHeight": "60vh", "overflowY": "auto"})
    raise dash.exceptions.PreventUpdate

# ---- Play local MP4 if Glasgow selected --------------------------------------
@app.callback(
    Output("video-container", "children"),
    Input("trend-region-select", "value")
)
def play_local_mp4(region):
    if region == "Glasgow":
        return html.Video(
            src="/assets/bogeyman.mp4",   # local MP4 in assets/
            autoPlay=True,
            controls=True,
            style={"width": "560px", "height": "315px"}
        )
    return ""

# ---- Auto open browser when app starts --------------------------------------
def open_browser():
    webbrowser.open_new("http://127.0.0.1:8050/")

if __name__ == "__main__":
    Timer(1, open_browser).start()
    app.run(debug=False)

