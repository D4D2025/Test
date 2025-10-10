'''
Created on 9 Oct 2025

@author: T-RexPO
'''
import plotly.graph_objects as go
import numpy as np
from math import radians, sin, cos, asin, sqrt
import tkinter as tk
from tkinter import Toplevel, Label, PhotoImage
from threading import Thread
from playsound import playsound
import os
import sys
import time

# --------------------------------------------------------------------
# Determine script directory for safe file lookup
# --------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

# --------------------------------------------------------------------
# Safe sound player
# --------------------------------------------------------------------
def safe_playsound(file):
    """Play sound safely if file exists."""
    full_path = file if os.path.isabs(file) else os.path.join(SCRIPT_DIR, file)
    if os.path.exists(full_path):
        try:
            Thread(target=lambda: playsound(full_path), daemon=True).start()
        except Exception as e:
            print(f"[Sound playback error] {e}")
    else:
        print(f"[Sound skipped] File not found: {full_path}")

# --------------------------------------------------------------------
# UK Cities (approximate coordinates)
# --------------------------------------------------------------------
cities = {
    "Edinburgh":  {"lat": 55.9533, "lon": -3.1883, "color": "red"},
    "Glasgow":    {"lat": 55.8642, "lon": -4.2518, "color": "blue"},
    "Newcastle":  {"lat": 54.9784, "lon": -1.6174, "color": "green"},
    "Birmingham": {"lat": 52.4862, "lon": -1.8904, "color": "orange"},
    "London":     {"lat": 51.5074, "lon": -0.1278, "color": "purple"},
}

# --------------------------------------------------------------------
# Distance + interpolation helpers
# --------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance (km) between two coordinates."""
    R = 6371
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon / 2)**2
    return 2 * R * asin(sqrt(a))

def interpolate_points(a, b, n_steps):
    """Linear interpolation between cities a and b."""
    lat1, lon1 = cities[a]["lat"], cities[a]["lon"]
    lat2, lon2 = cities[b]["lat"], cities[b]["lon"]
    lats = np.linspace(lat1, lat2, n_steps)
    lons = np.linspace(lon1, lon2, n_steps)
    return list(zip(lats, lons))

# --------------------------------------------------------------------
# Journey plan (Glasgow → Newcastle → Birmingham → London)
# --------------------------------------------------------------------
journey_order = ["Glasgow", "Newcastle", "Birmingham", "London"]

legs = []
for dest in journey_order:
    dist = haversine(cities["Edinburgh"]["lat"], cities["Edinburgh"]["lon"],
                     cities[dest]["lat"], cities[dest]["lon"])
    moves = max(3, int(dist / 20))
    legs.append((dest, moves))

# --------------------------------------------------------------------
# Generate sequential path with totals
# --------------------------------------------------------------------
lat_points, lon_points, day_counts, step_sums = [], [], [], []
day_counter = 0
total_steps = 0
steps_per_km = 1500
km_per_move = 20
steps_per_move = steps_per_km * km_per_move

for dest, moves in legs:
    # Outbound
    for lat, lon in interpolate_points("Edinburgh", dest, moves):
        day_counter += 1
        lat_points.append(lat)
        lon_points.append(lon)
        day_counts.append(day_counter)
        step_sums.append(total_steps)
    # Pause at destination
    for _ in range(3):
        day_counter += 1
        lat_points.append(cities[dest]["lat"])
        lon_points.append(cities[dest]["lon"])
        day_counts.append(day_counter)
        step_sums.append(total_steps)
    # Return
    for lat, lon in interpolate_points(dest, "Edinburgh", moves):
        day_counter += 1
        lat_points.append(lat)
        lon_points.append(lon)
        day_counts.append(day_counter)
        step_sums.append(total_steps)
    total_steps += (moves * 2 * steps_per_move)
    for _ in range(3):
        day_counter += 1
        lat_points.append(cities["Edinburgh"]["lat"])
        lon_points.append(cities["Edinburgh"]["lon"])
        day_counts.append(day_counter)
        step_sums.append(total_steps)

lat_points, lon_points, day_counts, step_sums = (
    lat_points[:180], lon_points[:180], day_counts[:180], step_sums[:180]
)

# --------------------------------------------------------------------
# Popup shown AFTER Glasgow round trip completion
# --------------------------------------------------------------------
def show_popup_after_delay():
    # Calculate realistic delay: Glasgow moves * 2 + 6 pauses → * 5 seconds
    glasgow_moves = next(m for d, m in legs if d == "Glasgow")
    total_delay = (glasgow_moves * 2 + 6) * 5  # seconds
    print(f"[Popup scheduled] Showing after {total_delay:.1f} seconds")
    time.sleep(total_delay)  # Wait while animation runs

    try:
        # Play sound
        safe_playsound("applause.wav")

        # Display popup window
        root = tk.Tk()
        root.withdraw()
        popup = Toplevel(root)
        popup.title("Motivation")
        popup.geometry("400x300")
        popup.configure(bg="white")

        img_path = os.path.join(SCRIPT_DIR, "your_image.png")
        img = PhotoImage(file=img_path)
        img_label = Label(popup, image=img, bg="white")
        img_label.image = img
        img_label.pack(pady=10)

        text_label = Label(
            popup,
            text="You're doing a good job...",
            font=("Arial", 14, "bold"),
            bg="white",
            fg="darkgreen"
        )
        text_label.pack(pady=10)

        popup.after(5000, popup.destroy)
        root.after(5500, root.destroy)
        root.mainloop()
    except Exception as e:
        print(f"[Popup failed] {e}")

# Start popup in background thread (so it doesn't block map opening)
Thread(target=show_popup_after_delay, daemon=True).start()

# --------------------------------------------------------------------
# Build the Plotly animation
# --------------------------------------------------------------------
fig = go.Figure()

for city in journey_order:
    fig.add_trace(go.Scattergeo(
        lon=[cities["Edinburgh"]["lon"], cities[city]["lon"]],
        lat=[cities["Edinburgh"]["lat"], cities[city]["lat"]],
        mode="lines",
        line=dict(width=2, color=cities[city]["color"]),
        opacity=0.6,
        showlegend=False
    ))

for name, info in cities.items():
    fig.add_trace(go.Scattergeo(
        lon=[info["lon"]],
        lat=[info["lat"]],
        text=name,
        mode="markers+text",
        textposition="top center",
        marker=dict(size=8, color=info["color"], line=dict(width=1, color="white")),
        showlegend=False
    ))

walker_trace = go.Scattergeo(
    lon=[lon_points[0]], lat=[lat_points[0]],
    mode="text", text=["🚶"], textfont=dict(size=26), showlegend=False
)
day_trace = go.Scattergeo(
    lon=[lon_points[0]], lat=[lat_points[0] + 0.3],
    mode="text", text=[f"Day {day_counts[0]}"],
    textfont=dict(size=12, color="black"), showlegend=False
)
sum_trace = go.Scattergeo(
    lon=[lon_points[0]], lat=[lat_points[0] + 0.6],
    mode="text", text=[f"Total {step_sums[0]:,} steps"],
    textfont=dict(size=12, color="darkred"), showlegend=False
)
fig.add_trace(walker_trace)
fig.add_trace(day_trace)
fig.add_trace(sum_trace)
walker_indices = [len(fig.data) - 3, len(fig.data) - 2, len(fig.data) - 1]

frames = []
for i in range(len(lat_points)):
    lat, lon = lat_points[i], lon_points[i]
    day = day_counts[i]
    total = step_sums[i]
    frame_data = [
        go.Scattergeo(lon=[lon], lat=[lat], mode="text", text=["🚶"], textfont=dict(size=26)),
        go.Scattergeo(lon=[lon], lat=[lat + 0.3],
                      mode="text", text=[f"Day {day}"], textfont=dict(size=12, color="black")),
        go.Scattergeo(lon=[lon], lat=[lat + 0.6],
                      mode="text", text=[f"Total {total:,} steps"], textfont=dict(size=12, color="darkred")),
    ]
    frames.append(go.Frame(data=frame_data, name=str(i), traces=walker_indices))

fig.frames = frames

fig.update_layout(
    title="Robert's Steps Challenge",
    geo=dict(
        projection_type="mercator",
        showland=True,
        landcolor="rgb(235,240,230)",
        showcountries=True,
        countrycolor="gray",
        showcoastlines=True,
        coastlinecolor="gray",
        showframe=False,
        lonaxis=dict(range=[-6.5, 2]),
        lataxis=dict(range=[50, 59])
    ),
    updatemenus=[{
        "type": "buttons",
        "x": 0.05, "y": -0.05,
        "buttons": [
            {
                "label": "▶ Play",
                "method": "animate",
                "args": [None, {
                    "frame": {"duration": 5000, "redraw": True},
                    "transition": {"duration": 0},
                    "fromcurrent": True,
                    "mode": "immediate",
                    "loop": False
                }]
            },
            {
                "label": "⏸ Pause",
                "method": "animate",
                "args": [[None], {"frame": {"duration": 0}, "mode": "immediate"}]
            }
        ]
    }],
    margin=dict(l=0, r=0, t=60, b=0),
    showlegend=False
)

fig.show()











