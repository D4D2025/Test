'''
Created on 27 Oct 2025

@author: RexPO
'''
# prisoners_dilemma_tool.py
# A small Tkinter + Matplotlib GUI for exploring the Prisoner's Dilemma.
# - You enter prison-years (lower is better) for A and B in each of the four outcomes.
# - The app computes best responses, dominant strategies, and pure-strategy Nash equilibria.
# - It renders three charts: A's outcomes, B's outcomes, and a heatmap of total years.
# - "Play a Round" lets Player A pick c/d; Player B is random; shows the realized outcome.
# - NEW: Enter/Update Payoffs now always pre-fills the classic PD numbers by default.
#
# Requirements: Python 3.x, matplotlib
#   pip install matplotlib

import tkinter as tk
from tkinter import messagebox, simpledialog
from dataclasses import dataclass
from typing import Dict, Tuple, List, Optional

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

ACTIONS = ["C", "D"]  # Internally: C=Cooperate, D=Defect

def pretty_action(a: str) -> str:
    return "Cooperate" if a == "C" else "Defect"

@dataclass
class Payoffs:
    # prison years by outcome: (A_action, B_action) -> (years_A, years_B)
    data: Dict[Tuple[str, str], Tuple[float, float]]

    @staticmethod
    def default():
        # Classic PD example (years in prison: lower is better)
        # (C,C): both 1
        # (A D, B C): A 0, B 3
        # (A C, B D): A 3, B 0
        # (D,D): both 2
        return Payoffs({
            ("C", "C"): (1.0, 1.0),
            ("D", "C"): (0.0, 3.0),
            ("C", "D"): (3.0, 0.0),
            ("D", "D"): (2.0, 2.0),
        })

    def a_years(self, a: str, b: str) -> float:
        return self.data[(a, b)][0]

    def b_years(self, a: str, b: str) -> float:
        return self.data[(a, b)][1]

class PDApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Prisoner’s Dilemma – Decision Analytics Tool")
        self.geometry("1180x880")
        self.minsize(1060, 800)

        self.payoffs = Payoffs.default()

        # --- Top Controls ---
        top = tk.Frame(self, padx=10, pady=10)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Label(top, text="Prisoner’s Dilemma Tool", font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)

        btn_enter = tk.Button(top, text="Enter/Update Payoffs…", command=self.enter_payoffs)
        btn_enter.pack(side=tk.LEFT, padx=10)

        btn_analyze = tk.Button(top, text="Analyze", command=self.run_analysis)
        btn_analyze.pack(side=tk.LEFT, padx=10)

        # Play a round (A chooses c/d; B random)
        btn_play = tk.Button(top, text="Play a Round", command=self.play_round)
        btn_play.pack(side=tk.LEFT, padx=10)

        btn_reset = tk.Button(top, text="Reset to Classic PD", command=self.reset_default)
        btn_reset.pack(side=tk.LEFT, padx=10)

        # --- Recommendation / Explanation ---
        self.rec_frame = tk.LabelFrame(self, text="Recommendation & Analysis", padx=10, pady=8)
        self.rec_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))

        # Larger font for clarity
        self.lbl_summary = tk.Label(self.rec_frame, text="", justify=tk.LEFT, font=("Segoe UI", 12))
        self.lbl_summary.pack(fill=tk.X)

        # --- Charts area ---
        charts = tk.Frame(self)
        charts.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=6)

        self.fig_a, self.ax_a = plt.subplots(figsize=(5.4, 3.6))
        self.canvas_a = FigureCanvasTkAgg(self.fig_a, master=charts)
        self.canvas_a.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))

        self.fig_b, self.ax_b = plt.subplots(figsize=(5.4, 3.6))
        self.canvas_b = FigureCanvasTkAgg(self.fig_b, master=charts)
        self.canvas_b.get_tk_widget().grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))

        self.fig_h, self.ax_h = plt.subplots(figsize=(11.2, 4.2))
        self.canvas_h = FigureCanvasTkAgg(self.fig_h, master=charts)
        self.canvas_h.get_tk_widget().grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))

        charts.grid_rowconfigure(0, weight=1)
        charts.grid_rowconfigure(1, weight=1)
        charts.grid_columnconfigure(0, weight=1)
        charts.grid_columnconfigure(1, weight=1)

        # Initial analysis / plots
        self.run_analysis()

    def reset_default(self):
        self.payoffs = Payoffs.default()
        self.run_analysis()

    def enter_payoffs(self):
        """
        Pop-up dialogs to collect prison years for A and B in each outcome.
        The user who starts entering values is Player A (A’s years are always asked first).
        Lower is better (years in prison).

        NEW: This dialog now always pre-fills with the classic PD numbers,
        so you can just press OK or tweak them each time.
        """
        def ask_float(title, prompt, initial):
            val = simpledialog.askfloat(title, prompt, initialvalue=initial, parent=self)
            if val is None:
                raise KeyboardInterrupt  # user cancelled
            if val < 0:
                messagebox.showerror("Invalid value", "Years cannot be negative.")
                raise ValueError("Negative years")
            return float(val)

        try:
            # Always use classic defaults as initial values (per user request),
            # regardless of the current matrix state.
            classic = Payoffs.default().data

            # (C, C)
            a_cc = ask_float(
                "Enter Payoff (A: Cooperate, B: Cooperate) – A",
                "Player A years (A Cooperates, B Cooperates):",
                classic[("C", "C")][0]
            )
            b_cc = ask_float(
                "Enter Payoff (A: Cooperate, B: Cooperate) – B",
                "Player B years (A Cooperates, B Cooperates):",
                classic[("C", "C")][1]
            )

            # (D, C)
            a_dc = ask_float(
                "Enter Payoff (A: Defect, B: Cooperate) – A",
                "Player A years (A Defects, B Cooperates):",
                classic[("D", "C")][0]
            )
            b_dc = ask_float(
                "Enter Payoff (A: Defect, B: Cooperate) – B",
                "Player B years (A Defects, B Cooperates):",
                classic[("D", "C")][1]
            )

            # (C, D)
            a_cd = ask_float(
                "Enter Payoff (A: Cooperate, B: Defect) – A",
                "Player A years (A Cooperates, B Defects):",
                classic[("C", "D")][0]
            )
            b_cd = ask_float(
                "Enter Payoff (A: Cooperate, B: Defect) – B",
                "Player B years (A Cooperates, B Defects):",
                classic[("C", "D")][1]
            )

            # (D, D)
            a_dd = ask_float(
                "Enter Payoff (A: Defect, B: Defect) – A",
                "Player A years (A Defects, B Defects):",
                classic[("D", "D")][0]
            )
            b_dd = ask_float(
                "Enter Payoff (A: Defect, B: Defect) – B",
                "Player B years (A Defects, B Defects):",
                classic[("D", "D")][1]
            )

            self.payoffs = Payoffs({
                ("C", "C"): (a_cc, b_cc),
                ("D", "C"): (a_dc, b_dc),
                ("C", "D"): (a_cd, b_cd),
                ("D", "D"): (a_dd, b_dd),
            })
            self.run_analysis()

        except KeyboardInterrupt:
            return
        except ValueError:
            return

    # ---------- Play a round (A picks c/d, B random) ----------

    def play_round(self):
        """
        Lets Player A choose c/d without knowing B's move.
        B's move is drawn at random with equal probability.
        Shows a pop-up with the realized outcome using the current payoff matrix.
        """
        move_a = simpledialog.askstring(
            "Player A move",
            "Enter your move (c for cooperate, d for defect):",
            parent=self
        )
        if move_a is None:
            return  # cancelled
        move_a = move_a.strip().lower()
        if move_a not in ("c", "d"):
            messagebox.showerror("Invalid move", "Please enter 'c' or 'd'.")
            return

        move_b = np.random.choice(["c", "d"])  # equally likely by default

        a = move_a.upper()
        b = move_b.upper()

        a_years = self.payoffs.a_years(a, b)
        b_years = self.payoffs.b_years(a, b)

        messagebox.showinfo(
            "Round Result",
            f"A chose: {pretty_action(a)}\n"
            f"B chose: {pretty_action(b)}\n\n"
            f"Outcome (from current payoff matrix):\n"
            f"  A serves {a_years:.2f} years\n"
            f"  B serves {b_years:.2f} years"
        )
        # Analysis remains unchanged; we do not alter the matrix here.

    # ---------- Core analytics ----------

    def best_responses(self) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        Returns best responses for A and B.
        A_br[b_action] -> list of A actions minimizing A's prison years given B's action.
        B_br[a_action] -> list of B actions minimizing B's prison years given A's action.
        """
        A_br: Dict[str, List[str]] = {}
        B_br: Dict[str, List[str]] = {}

        # A's best responses to B's action
        for b in ACTIONS:
            outcomes = {a: self.payoffs.a_years(a, b) for a in ACTIONS}
            min_years = min(outcomes.values())
            A_br[b] = [a for a, y in outcomes.items() if np.isclose(y, min_years)]
        # B's best responses to A's action
        for a in ACTIONS:
            outcomes = {b: self.payoffs.b_years(a, b) for b in ACTIONS}
            min_years = min(outcomes.values())
            B_br[a] = [b for b, y in outcomes.items() if np.isclose(y, min_years)]
        return A_br, B_br

    def pure_strategy_NE(self, A_br, B_br) -> List[Tuple[str, str]]:
        """
        Pure-strategy Nash equilibria are profiles (a,b) where:
            a ∈ A_br[b] and b ∈ B_br[a].
        """
        ne = []
        for a in ACTIONS:
            for b in ACTIONS:
                if (a in A_br[b]) and (b in B_br[a]):
                    ne.append((a, b))
        return ne

    def dominant_strategy(self, br_map: Dict[str, List[str]]) -> Optional[str]:
        """
        If the same action is a best response to both possible actions of the other player,
        there is a dominant strategy (may be weak or strict). Return 'C' or 'D' (or 'C/D' if degenerate).
        """
        common = set(br_map[ACTIONS[0]]).intersection(set(br_map[ACTIONS[1]]))
        if len(common) == 1:
            return list(common)[0]
        elif len(common) > 1:
            return "/".join(sorted(common))
        return None

    def minimax_for_A(self) -> str:
        """
        Robust fallback: choose A's action that minimizes the worst-case (max over B) prison years.
        Returns 'C' or 'D'.
        """
        worst_if_C = max(self.payoffs.a_years("C", "C"), self.payoffs.a_years("C", "D"))
        worst_if_D = max(self.payoffs.a_years("D", "C"), self.payoffs.a_years("D", "D"))
        if np.isclose(worst_if_C, worst_if_D):
            # tie-break toward Cooperation for social preference if equal worst-case
            return "C"
        return "C" if worst_if_C < worst_if_D else "D"

    # ---------- UI: analysis & plots ----------

    def run_analysis(self):
        A_br, B_br = self.best_responses()
        ne = self.pure_strategy_NE(A_br, B_br)
        A_dom = self.dominant_strategy(A_br)
        B_dom = self.dominant_strategy(B_br)

        # Recommendation for A first
        recommended_a_reason = ""
        if A_dom and len(A_dom) == 1:
            recommended_a = A_dom
            recommended_a_reason = "A has a dominant strategy"
        elif ne:
            recommended_a = ne[0][0]
            recommended_a_reason = "derived from the pure-strategy Nash equilibrium"
        else:
            recommended_a = self.minimax_for_A()
            recommended_a_reason = "robust minimax (minimise A’s worst-case years)"

        # Compose natural-language summary & recommendation
        lines = []
        # Clarify C/D upfront
        lines.append("Legend: C = Cooperate, D = Defect. Rows (vertical) are A’s choices; columns (horizontal) are B’s.")
        lines.append("You are Player A (you enter values for A first in each dialog).")
        lines.append("")

        # Best responses phrased in words + numbers for A then B
        for b in ACTIONS:
            a_choices = " or ".join(pretty_action(a) for a in A_br[b])
            yrs = {a: self.payoffs.a_years(a, b) for a in ACTIONS}
            comp = (f"If B {pretty_action(b).lower()}s, A should choose {a_choices} "
                    f"(A years: Cooperate→{yrs['C']:.2f}, Defect→{yrs['D']:.2f}).")
            lines.append(comp)
        for a in ACTIONS:
            b_choices = " or ".join(pretty_action(b) for b in B_br[a])
            yrs = {b: self.payoffs.b_years(a, b) for b in ACTIONS}
            comp = (f"If A {pretty_action(a).lower()}s, B should choose {b_choices} "
                    f"(B years: Cooperate→{yrs['C']:.2f}, Defect→{yrs['D']:.2f}).")
            lines.append(comp)

        # Dominant strategies
        lines.append(f"A’s dominant strategy: {pretty_action(A_dom) if A_dom and len(A_dom)==1 else ('none' if not A_dom else A_dom)}.")
        lines.append(f"B’s dominant strategy: {pretty_action(B_dom) if B_dom and len(B_dom)==1 else ('none' if not B_dom else B_dom)}.")

        # Nash equilibria
        if ne:
            pretty_ne = ", ".join([f"({pretty_action(a)[0]}/{pretty_action(a)}, {pretty_action(b)[0]}/{pretty_action(b)})"
                                   for a, b in ne])
            lines.append(f"Pure-strategy Nash equilibrium (NE): {pretty_ne}.")
        else:
            lines.append("No pure-strategy Nash equilibrium.")

        # Final recommendation for A (explicit)
        lines.append(f"Final recommendation for Player A: **{pretty_action(recommended_a)}** ({recommended_a_reason}).")

        self.lbl_summary.config(text="\n".join(lines))

        # Update charts
        self.plot_A_outcomes(A_br)
        self.plot_B_outcomes(B_br)
        self.plot_heatmap(ne, (recommended_a, None))  # pass A’s recommendation for highlighting row if useful

    def plot_A_outcomes(self, A_br):
        self.ax_a.clear()

        a_c_if_bC = self.payoffs.a_years("C", "C")
        a_d_if_bC = self.payoffs.a_years("D", "C")
        a_c_if_bD = self.payoffs.a_years("C", "D")
        a_d_if_bD = self.payoffs.a_years("D", "D")

        labels = [
            "A: Cooperate | B: Cooperate",
            "A: Defect    | B: Cooperate",
            "A: Cooperate | B: Defect",
            "A: Defect    | B: Defect",
        ]
        values = [a_c_if_bC, a_d_if_bC, a_c_if_bD, a_d_if_bD]

        bars = self.ax_a.bar(labels, values)
        self.ax_a.set_ylabel("A's prison years (lower is better)")
        self.ax_a.set_title("A’s outcomes across B’s actions (best responses marked)")

        # Emphasize best responses with a marker above the bar
        best_bC = A_br["C"]
        best_bD = A_br["D"]
        idxs = []
        idxs += [0] if "C" in best_bC else []
        idxs += [1] if "D" in best_bC else []
        idxs += [2] if "C" in best_bD else []
        idxs += [3] if "D" in best_bD else []
        for i in idxs:
            h = bars[i].get_height()
            self.ax_a.text(i, h + max(values)*0.03 if values else 0.1, "★ best", ha="center", va="bottom")

        self.ax_a.set_ylim(0, max(values)*1.25 if values else 1.0)
        self.ax_a.tick_params(axis='x', rotation=15)
        self.fig_a.tight_layout()
        self.canvas_a.draw_idle()

    def plot_B_outcomes(self, B_br):
        self.ax_b.clear()

        b_c_if_aC = self.payoffs.b_years("C", "C")
        b_d_if_aC = self.payoffs.b_years("C", "D")
        b_c_if_aD = self.payoffs.b_years("D", "C")
        b_d_if_aD = self.payoffs.b_years("D", "D")

        labels = [
            "B: Cooperate | A: Cooperate",
            "B: Defect    | A: Cooperate",
            "B: Cooperate | A: Defect",
            "B: Defect    | A: Defect",
        ]
        values = [b_c_if_aC, b_d_if_aC, b_c_if_aD, b_d_if_aD]

        bars = self.ax_b.bar(labels, values)
        self.ax_b.set_ylabel("B's prison years (lower is better)")
        self.ax_b.set_title("B’s outcomes across A’s actions (best responses marked)")

        best_aC = B_br["C"]
        best_aD = B_br["D"]
        idxs = []
        idxs += [0] if "C" in best_aC else []
        idxs += [1] if "D" in best_aC else []
        idxs += [2] if "C" in best_aD else []
        idxs += [3] if "D" in best_aD else []
        for i in idxs:
            h = bars[i].get_height()
            self.ax_b.text(i, h + max(values)*0.03 if values else 0.1, "★ best", ha="center", va="bottom")

        self.ax_b.set_ylim(0, max(values)*1.25 if values else 1.0)
        self.ax_b.tick_params(axis='x', rotation=15)
        self.fig_b.tight_layout()
        self.canvas_b.draw_idle()

    def plot_heatmap(self, ne: List[Tuple[str, str]], rec: Optional[Tuple[str, Optional[str]]]):
        """
        Heatmap of total (A+B) years.
        Rows (vertical) = A's actions [Cooperate, Defect]
        Columns (horizontal) = B's actions [Cooperate, Defect]
        """
        self.ax_h.clear()

        grid = np.zeros((2, 2), dtype=float)
        cell_text = [["", ""], ["", ""]]
        for i, a in enumerate(ACTIONS):
            for j, b in enumerate(ACTIONS):
                a_y = self.payoffs.a_years(a, b)
                b_y = self.payoffs.b_years(a, b)
                grid[i, j] = a_y + b_y
                cell_text[i][j] = f"A:{a_y:.2f}\nB:{b_y:.2f}"

        im = self.ax_h.imshow(grid, aspect="equal")
        self.ax_h.set_xticks([0, 1], labels=["B: Cooperate", "B: Defect"])
        self.ax_h.set_yticks([0, 1], labels=["A: Cooperate", "A: Defect"])
        self.ax_h.set_title("Outcome matrix — rows: A (Cooperate/Defect), columns: B (Cooperate/Defect)")

        # Annotate each cell with A/B values
        for i in range(2):
            for j in range(2):
                self.ax_h.text(j, i, cell_text[i][j], ha="center", va="center", fontsize=10,
                               bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7))

        # Outline Nash equilibria cells (if any)
        for a, b in ne:
            i = 0 if a == "C" else 1
            j = 0 if b == "C" else 1
            self.ax_h.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, fill=False, lw=3))

        # Emphasize A’s recommended action by thick border around the whole row if no NE used
        if rec is not None:
            a_rec, b_rec = rec  # b_rec may be None when recommendation is only for A
            i = 0 if a_rec == "C" else 1
            if b_rec in ("C", "D"):
                j = 0 if b_rec == "C" else 1
                self.ax_h.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, fill=False, lw=4.5))
            else:
                self.ax_h.add_patch(plt.Rectangle((-0.5, i-0.5), 2, 1, fill=False, lw=4.5))

        self.fig_h.colorbar(im, ax=self.ax_h, shrink=0.9, label="Total years (A+B)")
        self.fig_h.tight_layout()
        self.canvas_h.draw_idle()

if __name__ == "__main__":
    app = PDApp()
    app.mainloop()

