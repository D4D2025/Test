'''
Created on 27 Oct 2025

@author: T-RexPO
'''
# pareto_service_tool.py
# Pareto Efficiency Tool for Service Management (Tkinter + Matplotlib)
# - Fixed to 5 services named S1..S5 with labels "(Service1..Service5)".
# - User enters per-service: Users Affected, Incidents, Problems, Changes, Service Manager, Resolver Team.
# - Objectives (minimise): [Users Affected, Incidents+Problems, Changes].
# - Outputs final statement + recommendation describing actions to reach Pareto efficiency;
#   if already Pareto-efficient, states that no further Pareto improvements exist (trade-offs required).
# - Charts:
#   * 3D Pareto View: Users Affected vs Incidents/Problems (Inc+Prob) vs Changes
#   * 2D Projection: Users Affected vs Incidents/Problems (Inc+Prob), bubbles sized by Changes
#   * Bar Chart: Resolver Teams — stacked Incidents and Changes

import tkinter as tk
from tkinter import simpledialog, messagebox
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


# ----------------------------- Data Model -----------------------------

@dataclass
class ServiceRecord:
    name: str
    users_affected: float
    incidents: float
    problems: float
    changes: float
    service_manager: str
    resolver_team: str


@dataclass
class Dataset:
    services: List[ServiceRecord] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        if not self.services:
            return pd.DataFrame(columns=[
                "Service", "Users Affected", "Incidents", "Problems", "Inc+Prob",
                "Changes", "Service Manager", "Resolver Team"
            ])
        rows = []
        for s in self.services:
            rows.append({
                "Service": s.name,
                "Users Affected": float(s.users_affected),
                "Incidents": float(s.incidents),
                "Problems": float(s.problems),
                "Inc+Prob": float(s.incidents + s.problems),
                "Changes": float(s.changes),
                "Service Manager": s.service_manager,
                "Resolver Team": s.resolver_team
            })
        return pd.DataFrame(rows)


# ----------------------------- Pareto Logic -----------------------------

def pareto_front_bool(points: np.ndarray) -> np.ndarray:
    """
    Compute Pareto front (minimisation). points shape: (n, d).
    Returns boolean mask True for Pareto-efficient points.
    """
    n = points.shape[0]
    is_eff = np.ones(n, dtype=bool)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # j dominates i if j <= i in all dims and < in at least one
            if np.all(points[j] <= points[i]) and np.any(points[j] < points[i]):
                is_eff[i] = False
                break
    return is_eff


def dominators(points: np.ndarray, names: List[str]) -> Dict[str, List[str]]:
    """
    For each point i, list names of services that dominate it.
    """
    n = points.shape[0]
    dom: Dict[str, List[str]] = {names[i]: [] for i in range(n)}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if np.all(points[j] <= points[i]) and np.any(points[j] < points[i]):
                dom[names[i]].append(names[j])
    return dom


# ----------------------------- GUI App -----------------------------

class ParetoApp(tk.Tk):
    SERVICE_NAMES = [
        "S1 (Service1)",
        "S2 (Service2)",
        "S3 (Service3)",
        "S4 (Service4)",
        "S5 (Service5)",
    ]

    def __init__(self):
        super().__init__()
        self.title("Pareto Efficiency Tool — Service Management")
        self.geometry("1400x960")
        self.minsize(1280, 900)

        self.dataset = Dataset()

        # Top controls
        top = tk.Frame(self, padx=10, pady=10)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Label(top, text="Pareto Efficiency (Users • Incidents/Problems • Changes)",
                 font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)

        tk.Button(top, text="Enter/Update Data…", command=self.enter_data).pack(side=tk.LEFT, padx=10)
        tk.Button(top, text="Analyze", command=self.run_analysis).pack(side=tk.LEFT, padx=6)
        tk.Button(top, text="Reset to Demo", command=self.reset_demo).pack(side=tk.LEFT, padx=6)

        # Final statement / recommendation
        self.panel = tk.LabelFrame(self, text="Final Statement & Recommendation", padx=10, pady=10)
        self.panel.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))

        self.out_label = tk.Label(self.panel, text="", justify=tk.LEFT, font=("Segoe UI", 12))
        self.out_label.pack(fill=tk.X)

        # Chart area
        chart_frame = tk.Frame(self)
        chart_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Create a 2x2 grid: 3D, 2D, and bar chart span nicely
        self.fig = plt.Figure(figsize=(12.8, 7.8))
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1, 1.05])

        self.ax3d = self.fig.add_subplot(gs[0, 0], projection='3d')
        self.ax2d = self.fig.add_subplot(gs[0, 1])
        self.ax_bar = self.fig.add_subplot(gs[1, :])

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Seed with a demo dataset
        self.reset_demo()
        self.run_analysis()

    # --------------------- Data Entry ---------------------

    def reset_demo(self):
        """
        Demo dataset (5 services). Users Affected, Incidents, Problems, Changes, SM, Team.
        Lower is better on Users/Inc+Prob/Changes.
        """
        demo_defaults = [
            ServiceRecord(self.SERVICE_NAMES[0], 1200, 55, 14, 45, "Alice Morgan", "Team3"),
            ServiceRecord(self.SERVICE_NAMES[1],  900, 40, 22, 30, "Brian Shaw",   "Team 2"),
            ServiceRecord(self.SERVICE_NAMES[2], 1500, 60, 11, 52, "Grace Lin",    "Team1"),
            ServiceRecord(self.SERVICE_NAMES[3],  800, 42, 16, 26, "Dana White",   "Team 2"),
            ServiceRecord(self.SERVICE_NAMES[4],  700, 35, 15, 40, "Eve Patel",    "Team3"),
        ]
        self.dataset = Dataset(demo_defaults)

    def enter_data(self):
        """
        Pop-ups to enter values for 5 fixed services S1..S5.
        User provides: Users Affected, Incidents, Problems, Changes, Service Manager, Resolver Team.
        Pre-fills with current values (or demo on first run).
        """
        if not self.dataset.services or len(self.dataset.services) != 5:
            self.reset_demo()

        try:
            new_records: List[ServiceRecord] = []
            for idx, svc_label in enumerate(self.SERVICE_NAMES):
                existing = self.dataset.services[idx]

                # Users Affected
                users = simpledialog.askfloat(
                    f"{svc_label} — Users Affected",
                    "Enter Users Affected (lower is better):",
                    initialvalue=existing.users_affected, parent=self
                )
                if users is None or users < 0:
                    raise KeyboardInterrupt

                # Incidents
                inc = simpledialog.askfloat(
                    f"{svc_label} — Incidents",
                    "Enter number of Incidents (lower is better):",
                    initialvalue=existing.incidents, parent=self
                )
                if inc is None or inc < 0:
                    raise KeyboardInterrupt

                # Problems
                prob = simpledialog.askfloat(
                    f"{svc_label} — Problems",
                    "Enter number of Problems (lower is better):",
                    initialvalue=existing.problems, parent=self
                )
                if prob is None or prob < 0:
                    raise KeyboardInterrupt

                # Service Manager
                sm = simpledialog.askstring(
                    f"{svc_label} — Service Manager",
                    "Enter Service Manager:",
                    initialvalue=existing.service_manager, parent=self
                )
                if sm is None:
                    raise KeyboardInterrupt

                # Changes
                chg = simpledialog.askfloat(
                    f"{svc_label} — Changes",
                    "Enter number of Changes (lower is better as risk/overhead proxy):",
                    initialvalue=existing.changes, parent=self
                )
                if chg is None or chg < 0:
                    raise KeyboardInterrupt

                # Resolver Team
                rt = simpledialog.askstring(
                    f"{svc_label} — Resolver Team",
                    "Enter Resolver Team:",
                    initialvalue=existing.resolver_team, parent=self
                )
                if rt is None:
                    raise KeyboardInterrupt

                new_records.append(ServiceRecord(
                    name=svc_label,
                    users_affected=float(users),
                    incidents=float(inc),
                    problems=float(prob),
                    changes=float(chg),
                    service_manager=sm.strip(),
                    resolver_team=rt.strip()
                ))

            self.dataset = Dataset(new_records)
            self.run_analysis()

        except KeyboardInterrupt:
            # Cancelled: keep previous data
            return

    # --------------------- Analysis & Plotting ---------------------

    def run_analysis(self):
        df = self.dataset.to_dataframe()
        if df.empty:
            self.out_label.config(text="No data. Click ‘Enter/Update Data…’ to add values.")
            self.clear_plots()
            return

        # Objectives (minimise): [Users Affected, Incidents+Problems, Changes]
        X = df[["Users Affected", "Inc+Prob", "Changes"]].to_numpy(dtype=float)
        names = df["Service"].tolist()

        eff_mask = pareto_front_bool(X)
        dom_map = dominators(X, names)

        efficient = df[eff_mask].copy()
        dominated = df[~eff_mask].copy()

        # Choose an "anchor" efficient option (lowest Users Affected, then Inc+Prob, then Changes)
        anchor_idx = None
        if not efficient.empty:
            eff_sorted = efficient.sort_values(by=["Users Affected", "Inc+Prob", "Changes"], ascending=[True, True, True])
            anchor_name = eff_sorted.iloc[0]["Service"]
            anchor_idx = names.index(anchor_name)
        else:
            anchor_name = None

        # Build final statement & recommendation
        lines: List[str] = []
        lines.append("Objectives (minimise): Users Affected • Incidents/Problems (Inc+Prob) • Changes.")
        lines.append("")

        if not efficient.empty:
            lines.append(f"Pareto-efficient services ({len(efficient)}): " +
                         ", ".join(efficient["Service"].tolist()) + ".")
        else:
            lines.append("No Pareto-efficient services detected (unusual with 5 services).")

        if not dominated.empty:
            lines.append("")
            lines.append("Dominated services (can be improved without harming others on all objectives):")
            for svc in dominated["Service"]:
                ds = dom_map.get(svc, [])
                if ds:
                    lines.append(f" • {svc} is dominated by: {', '.join(ds)}")
                else:
                    lines.append(f" • {svc} is dominated (dominators not resolved).")

        lines.append("")
        lines.append("Recommendation for Service Management:")

        if anchor_name:
            row = df[df["Service"] == anchor_name].iloc[0]
            lines.append(
                f" • Use **{anchor_name}** as the anchor Pareto option: "
                f"Users Affected={int(row['Users Affected'])}, Inc+Prob={int(row['Inc+Prob'])}, Changes={int(row['Changes'])}."
            )
            lines.append(
                f" • Maintain current performance for Pareto-efficient services; "
                f"further gains on any objective would worsen at least one other objective — "
                f"i.e., no Pareto improvement is available without trade-offs."
            )
            # Guidance for dominated services: directions to reach Pareto front
            if not dominated.empty:
                lines.append(" • For dominated services, reduce impact to move toward the Pareto front:")
                lines.append("    – Lower **Users Affected** via incident prevention and rapid mitigation;")
                lines.append("    – Reduce **Incidents/Problems** through root-cause elimination and backlog burn-down;")
                lines.append("    – Rationalise **Changes** (e.g., bundle, reduce failure risk) to decrease overhead.")
        else:
            lines.append(
                " • Pursue reductions in **Users Affected**, **Incidents/Problems**, and **Changes**. "
                "Aim to reach the Pareto front where no further improvement is possible without worsening another metric."
            )

        self.out_label.config(text="\n".join(lines))

        # Draw charts
        self.update_plots(df, eff_mask, anchor_idx)

    def clear_plots(self):
        self.ax3d.clear()
        self.ax2d.clear()
        self.ax_bar.clear()
        self.canvas.draw_idle()

    def update_plots(self, df: pd.DataFrame, eff_mask: np.ndarray, anchor_idx: Optional[int]):
        names = df["Service"].tolist()
        X = df[["Users Affected", "Inc+Prob", "Changes"]].to_numpy(dtype=float)

        # --- 3D Pareto View ---
        self.ax3d.clear()
        self.ax3d.set_title("3D Pareto View (lower is better)")
        self.ax3d.set_xlabel("Users Affected")
        self.ax3d.set_ylabel("Incidents/Problems (Inc+Prob)")
        self.ax3d.set_zlabel("Changes")

        dominated_idx = np.where(~eff_mask)[0]
        efficient_idx = np.where(eff_mask)[0]

        if dominated_idx.size:
            self.ax3d.scatter(X[dominated_idx, 0], X[dominated_idx, 1], X[dominated_idx, 2],
                              marker="o", alpha=0.5, s=55, label="Dominated")
        if efficient_idx.size:
            self.ax3d.scatter(X[efficient_idx, 0], X[efficient_idx, 1], X[efficient_idx, 2],
                              marker="^", alpha=0.9, s=75, label="Pareto-efficient")

        if anchor_idx is not None:
            self.ax3d.scatter(X[anchor_idx, 0], X[anchor_idx, 1], X[anchor_idx, 2],
                              marker="*", s=240, alpha=0.95, label=f"Anchor: {names[anchor_idx]}")
            self.ax3d.text(X[anchor_idx, 0], X[anchor_idx, 1], X[anchor_idx, 2],
                           f"  {names[anchor_idx]}")

        # >>> CHANGE 1: Move legend further left to avoid covering the 3D plot <<<
        self.ax3d.legend(loc="upper left", bbox_to_anchor=(-0.1, 1.0))

        # --- 2D Projection: Users Affected vs Incidents/Problems ---
        self.ax2d.clear()
        self.ax2d.set_title("2D Projection: Users Affected vs Incidents/Problems (bubble = Changes)")
        self.ax2d.set_xlabel("Users Affected")
        self.ax2d.set_ylabel("Incidents/Problems (Inc+Prob)")

        sizes = (df["Changes"].to_numpy(dtype=float) + 1.0) * 2.5

        if dominated_idx.size:
            self.ax2d.scatter(X[dominated_idx, 0], X[dominated_idx, 1],
                              s=sizes[dominated_idx], alpha=0.35, label="Dominated")
        if efficient_idx.size:
            self.ax2d.scatter(X[efficient_idx, 0], X[efficient_idx, 1],
                              s=sizes[efficient_idx], alpha=0.75, label="Pareto-efficient")
        if anchor_idx is not None:
            self.ax2d.scatter(X[anchor_idx, 0], X[anchor_idx, 1],
                              s=sizes[anchor_idx] * 1.8, marker="*", alpha=0.95,
                              label=f"Anchor: {names[anchor_idx]}")
            self.ax2d.annotate(names[anchor_idx],
                               (X[anchor_idx, 0], X[anchor_idx, 1]),
                               xytext=(6, 6), textcoords="offset points")

        # Label efficient (and small sets) for readability
        efficient_idx = set(np.where(eff_mask)[0].tolist())
        for i, nm in enumerate(names):
            if i == anchor_idx:
                continue
            if i in efficient_idx or len(names) <= 10:
                self.ax2d.annotate(nm, (X[i, 0], X[i, 1]), xytext=(4, 4),
                                   textcoords="offset points", fontsize=9)

        self.ax2d.legend(loc="best")
        self.ax2d.grid(True, alpha=0.25)

        # --- Bar Chart: Resolver Teams — Incidents & Changes ---
        self.ax_bar.clear()
        self.ax_bar.set_title("Resolver Teams — Resources vs Workload (Incidents & Changes)")
        self.ax_bar.set_xlabel("Resolver Team")
        self.ax_bar.set_ylabel("Count")

        # Aggregate per resolver team
        team_grp = df.groupby("Resolver Team").agg({
            "Incidents": "sum",
            "Changes": "sum"
        }).sort_index()

        teams = team_grp.index.tolist()
        inc_vals = team_grp["Incidents"].to_numpy()
        chg_vals = team_grp["Changes"].to_numpy()

        x = np.arange(len(teams))
        width = 0.6
        # Stacked bars: bottom = incidents, top = changes
        bars_inc = self.ax_bar.bar(x, inc_vals, width, label="Incidents", alpha=0.75)
        bars_chg = self.ax_bar.bar(x, chg_vals, width, bottom=inc_vals, label="Changes", alpha=0.65)

        # Annotate totals on top
        for xi, inc_v, chg_v in zip(x, inc_vals, chg_vals):
            total = inc_v + chg_v
            self.ax_bar.text(xi, total + max(1, total * 0.02), f"{int(total)}",
                             ha="center", va="bottom", fontsize=9)

        self.ax_bar.set_xticks(x, labels=teams, rotation=10)
        self.ax_bar.legend(loc="best")
        self.ax_bar.grid(axis="y", alpha=0.25)

        self.fig.tight_layout()
        self.canvas.draw_idle()


# ----------------------------- Main -----------------------------

if __name__ == "__main__":
    app = ParetoApp()
    app.mainloop()


