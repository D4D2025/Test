'''
Created on 1 Oct 2025

@author: T-RexPO
'''
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.express as px

import pandas as pd
import numpy as np
from datetime import datetime
import io
import base64
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
import webbrowser
from threading import Timer

# ---------- Config ----------
CSV_FILE = "servers.csv"   # path to CSV file
DB_CONN = "mysql+pymysql://user:password@localhost/dbname"  # MySQL connection string

# ---------- Data Loaders ----------
def generate_dummy_data(n=300):
    np.random.seed(None)
    return pd.DataFrame({
        "service": np.random.choice(["Service1", "Service2", "Service3", "Service4"], n),
        "server_type": np.random.choice(["ServerA", "ServerB", "ServerC", "ServerD"], n),
        "fault_fix_days": np.random.randint(1, 15, n),
        "fault_fix_time": np.random.randint(0, 24, n)
    })

def load_data_from_csv():
    try:
        return pd.read_csv(CSV_FILE)
    except Exception:
        return generate_dummy_data()

def load_data_from_db():
    try:
        engine = create_engine(DB_CONN)
        query = "SELECT service, server_type, fault_fix_days, fault_fix_time FROM servers"
        return pd.read_sql(query, engine)
    except Exception:
        return generate_dummy_data()

def get_data(source, simulate=True):
    if source == "CSV":
        return load_data_from_csv()
    elif source == "MySQL":
        return load_data_from_db()
    else:  # Simulated
        df = generate_dummy_data()
        if simulate:
            random_idx = np.random.choice(df.index, size=10, replace=False)
            df.loc[random_idx, "fault_fix_days"] += np.random.choice([-1, 0, 1], size=10)
            df["fault_fix_days"] = df["fault_fix_days"].clip(1, 20)
        return df

# ---------- Globals ----------
df_live = generate_dummy_data()
last_update_time = datetime.now().strftime("%H:%M:%S")
last_action = "Started at " + last_update_time
current_source = "Simulated"

# ---------- Dash App ----------
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.layout = html.Div([
    html.H1("Live IT Services & Servers Dashboard", style={"textAlign": "center"}),

    # -------- LIVE Indicator & Controls --------
    html.Div([
        html.Span("●", id="live-dot", style={"color": "red", "fontSize": "24px", "marginRight": "5px"}),
        html.Span("LIVE", id="live-label", style={"fontWeight": "bold", "fontSize": "20px", "marginRight": "10px"}),
        html.Span("STREAMING (Simulated)", id="live-status",
                  style={"color": "red", "fontWeight": "bold", "fontSize": "18px", "marginRight": "20px"}),

        html.Button("Pause", id="pause-play-btn", n_clicks=0, style={"marginLeft": "10px"}),
        html.Button("Reset Data", id="reset-btn", n_clicks=0,
                    style={"marginLeft": "10px", "backgroundColor": "#217346", "color": "white"}),
        html.Button("Export to PDF", id="export-pdf-btn", n_clicks=0,
                    style={"marginLeft": "10px", "backgroundColor": "#444", "color": "white"})
    ], style={"textAlign": "right", "marginRight": "20px"}),

    # -------- Data Source + Service/Server Selectors (same row) --------
    html.Div([
        html.Div([
            html.Label("Select Data Source:", style={"fontWeight": "bold"}),
            dcc.Dropdown(
                id="data-source",
                value="Simulated",
                options=[
                    {"label": "Simulated Dummy Data", "value": "Simulated"},
                    {"label": "CSV File", "value": "CSV"},
                    {"label": "MySQL Database", "value": "MySQL"},
                ],
                clearable=False,
                style={"width": "250px"}
            ),
            html.Div(id="data-source-info", style={"marginTop": "10px", "fontSize": "14px", "color": "teal"})
        ], className="four columns"),

        html.Div([
            html.Label("Choose service of interest:", style={"fontWeight": "bold"}),
            dcc.Dropdown(
                id='service-type',
                clearable=False,
                value="Service1",
                options=[{'label': x, 'value': x} for x in df_live["service"].unique()],
                style={"width": "250px"}
            )
        ], className="four columns"),

        html.Div([
            html.Label("Choose server of interest:", style={"fontWeight": "bold"}),
            dcc.Dropdown(
                id='server-type',
                clearable=False,
                value="ServerA",
                options=[{'label': x, 'value': x} for x in df_live["server_type"].unique()],
                style={"width": "250px"}
            )
        ], className="four columns"),
    ], className="row", style={"margin": "20px"}),

    # Timestamps and log
    html.Div(id="last-updated", style={"textAlign": "right", "marginRight": "20px", "fontSize": "14px", "color": "grey"}),
    html.Div(id="last-action", style={"textAlign": "right", "marginRight": "20px", "fontSize": "14px", "color": "blue"}),

    # Hidden download link
    html.Div(id="download-link"),

    html.Hr(),

    # -------- KPIs --------
    html.Div(id="kpi-div", className="row", style={"marginTop": "20px"}),

    html.Div(id="output-div", children=[]),

    # -------- Auto Refresh --------
    dcc.Interval(
        id="interval-component",
        interval=5*1000,
        n_intervals=0
    )
])


# ---------- Pause/Play ----------
@app.callback(
    [Output("interval-component", "disabled"),
     Output("pause-play-btn", "children"),
     Output("last-action", "children")],
    Input("pause-play-btn", "n_clicks"),
    prevent_initial_call=False
)
def toggle_stream(n_clicks):
    global last_action
    now = datetime.now().strftime("%H:%M:%S")
    if n_clicks % 2 == 1:
        last_action = f"Paused at {now}"
        return True, "Play", last_action
    else:
        last_action = f"Resumed at {now}"
        return False, "Pause", last_action


# ---------- Export to PDF ----------
@app.callback(
    Output("download-link", "children"),
    Input("export-pdf-btn", "n_clicks"),
    State("service-type", "value"),
    State("data-source", "value"),
    prevent_initial_call=True
)
def export_to_pdf(n_clicks, service_chosen, data_source):
    global df_live, last_action, last_update_time
    if n_clicks > 0:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(150, height - 40, "IT Services & Servers Dashboard Report")

        # Info
        c.setFont("Helvetica", 12)
        c.drawString(40, height - 70, f"Data Source: {data_source}")
        c.drawString(40, height - 90, f"Last Updated: {last_update_time}")
        c.drawString(40, height - 110, f"Last Action: {last_action}")

        # KPIs
        df_service = df_live[df_live["service"] == service_chosen]
        total_servers = len(df_live)
        total_service_servers = len(df_service)
        avg_fault_fix_days = round(df_service["fault_fix_days"].mean(), 2) if not df_service.empty else 0
        percent_service = round((total_service_servers / total_servers) * 100, 2) if total_servers > 0 else 0

        c.drawString(40, height - 150, f"Total Servers: {total_servers}")
        c.drawString(40, height - 170, f"Avg Fault Fix Days ({service_chosen}): {avg_fault_fix_days}")
        c.drawString(40, height - 190, f"% of Servers in {service_chosen}: {percent_service}%")
        c.drawString(40, height - 210, f"Servers in {service_chosen}: {total_service_servers}")

        c.save()
        buffer.seek(0)

        pdf_base64 = base64.b64encode(buffer.read()).decode("utf-8")
        href = f'<a href="data:application/pdf;base64,{pdf_base64}" download="servers_report.pdf">📄 Download PDF Report</a>'
        return html.Div([html.Hr(), html.Div(href, style={"textAlign": "center"})])

    return ""


# ---------- Update Dashboard ----------
@app.callback(
    [Output("kpi-div", "children"),
     Output("output-div", "children"),
     Output("live-dot", "style"),
     Output("live-label", "style"),
     Output("live-status", "children"),
     Output("live-status", "style"),
     Output("last-updated", "children"),
     Output("data-source-info", "children")],
    [Input("service-type", "value"),
     Input("server-type", "value"),
     Input("interval-component", "n_intervals"),
     Input("data-source", "value"),
     State("interval-component", "disabled")]
)
def update_dashboard(service_chosen, server_chosen, n, data_source, interval_disabled):
    global df_live, last_update_time, current_source
    current_source = data_source

    df_live = get_data(current_source, simulate=(not interval_disabled and current_source == "Simulated"))
    rows_loaded = len(df_live)

    last_update_time = datetime.now().strftime("%H:%M:%S")
    df_service = df_live[df_live["service"] == service_chosen]

    # ---------- KPIs ----------
    total_servers = len(df_live)
    total_service_servers = len(df_service)
    avg_fault_fix_days = round(df_service["fault_fix_days"].mean(), 2) if not df_service.empty else 0
    percent_service = round((total_service_servers / total_servers) * 100, 2) if total_servers > 0 else 0

    avg_color = "green" if avg_fault_fix_days < 5 else "orange" if avg_fault_fix_days <= 10 else "red"
    perc_color = "green" if percent_service > 40 else "orange" if percent_service >= 20 else "red"

    kpi_cards = [
        html.Div([
            html.H3("Total Servers", style={"textAlign": "center"}),
            html.H2(f"{total_servers}", style={"textAlign": "center", "color": "blue"})
        ], className="three columns", style={"border": "1px solid #ccc", "padding": "10px"}),

        html.Div([
            html.H3("Avg Fault Fix Days", style={"textAlign": "center"}),
            html.H2(f"{avg_fault_fix_days}", style={"textAlign": "center", "color": avg_color})
        ], className="three columns", style={"border": "1px solid #ccc", "padding": "10px"}),

        html.Div([
            html.H3(f"% of Servers in {service_chosen}", style={"textAlign": "center"}),
            html.H2(f"{percent_service}%", style={"textAlign": "center", "color": perc_color})
        ], className="three columns", style={"border": "1px solid #ccc", "padding": "10px"}),

        html.Div([
            html.H3(f"Servers in {service_chosen}", style={"textAlign": "center"}),
            html.H2(f"{total_service_servers}", style={"textAlign": "center", "color": "purple"})
        ], className="three columns", style={"border": "1px solid #ccc", "padding": "10px"}),
    ]

    # ---------- Charts ----------
    fig_hist = px.histogram(df_service, x="server_type", title="Count of Servers by Type")
    fig_strip = px.strip(df_service, x="server_type", y="fault_fix_days", title="Fault Fix Days per Server Type")
    fig_sunburst = px.sunburst(df_live, path=["service", "server_type"], title="Distribution of Servers per Service")
    fig_ecdf = px.ecdf(df_service, x="fault_fix_days", color="server_type", title="Probability Distribution of Fault Fix Days")
    df_line = df_service.groupby(["fault_fix_time", "server_type"]).size().reset_index(name="count")
    fig_line = px.line(df_line, x="fault_fix_time", y="count", color="server_type", markers=True,
                       title="Server Counts by Fault Fix Time")

    output_children = [
        html.Div([
            html.Div([dcc.Graph(figure=fig_hist)], className="six columns"),
            html.Div([dcc.Graph(figure=fig_strip)], className="six columns"),
        ], className="row"),

        html.H2("All Servers", style={"textAlign": "center"}),
        html.Hr(),

        html.Div([
            html.Div([dcc.Graph(figure=fig_sunburst)], className="six columns"),
            html.Div([dcc.Graph(figure=fig_ecdf)], className="six columns"),
        ], className="row"),

        html.Div([
            html.Div([dcc.Graph(figure=fig_line)], className="twelve columns"),
        ], className="row"),
    ]

    # --------- LIVE Indicator ---------
    if interval_disabled:
        dot_style = {"color": "orange", "fontSize": "24px", "marginRight": "5px", "opacity": 1}
        label_style = {"color": "orange", "fontWeight": "bold", "fontSize": "20px", "marginRight": "10px"}
        status_text = f"PAUSED ({current_source})"
        status_style = {"color": "orange", "fontWeight": "bold", "fontSize": "18px"}
    else:
        dot_style = {"color": "red", "fontSize": "24px", "marginRight": "5px",
                     "opacity": 1 if n % 2 == 0 else 0.2}
        label_style = {"color": "red", "fontWeight": "bold", "fontSize": "20px", "marginRight": "10px"}
        status_text = f"STREAMING ({current_source})"
        status_style = {"color": "red", "fontWeight": "bold", "fontSize": "18px"}

    last_updated_label = f"Last updated: {last_update_time}"
    source_info = f"Loaded {rows_loaded} rows from {current_source}"

    return kpi_cards, output_children, dot_style, label_style, status_text, status_style, last_updated_label, source_info


# ---------- Auto-open Browser ----------
if __name__ == '__main__':
    def open_browser():
        webbrowser.open_new("http://127.0.0.1:8050/")
    Timer(1, open_browser).start()
    app.run(debug=True, use_reloader=False)











