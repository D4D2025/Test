'''
Created on 14 Mar 2023

@author: Tim Rayner, Peter Odrobinski
'''
# Benford's Law goodness-of-fit for the first digit of a numeric column in an Excel file

# Benford's Law goodness-of-fit for the first digit of a numeric column in an Excel file
# Now with an interactive launcher and a popup explaining the chi-square decision rule.

import math
import sys
from pathlib import Path
from typing import List, Tuple, Optional, Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ---------------- Constants ----------------
BENFORD_PCT = [30.1, 17.6, 12.5, 9.7, 7.9, 6.7, 5.8, 5.1, 4.6]  # 1..9
CHI2_CRIT_8DF_0_05 = 15.507  # critical value for 8 d.f. at alpha=0.05


# ---------------- IO ----------------
def load_data(filename: Union[str, Path], column: str) -> pd.Series:
    """Load a column from an Excel file as numeric Series."""
    df = pd.read_excel(filename)
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found. Available: {list(df.columns)}")
    s = pd.to_numeric(df[column], errors="coerce")  # force numeric, turn non-numeric into NaN
    return s


# ---------------- Benford utilities ----------------
def leading_digit(x: float) -> Optional[int]:
    """Return the leading digit in {1..9} for a real number; None if not applicable."""
    if x is None or pd.isna(x):
        return None
    x = abs(float(x))
    if x == 0.0 or math.isinf(x) or math.isnan(x):
        return None
    # Scale to [1, 10)
    while x < 1:
        x *= 10.0
    while x >= 10:
        x /= 10.0
    d = int(x)
    return d if 1 <= d <= 9 else None


def count_first_digit(series: pd.Series, min_abs: Optional[float] = 1.0) -> Tuple[int, List[int], List[float]]:
    """
    Count first digits 1..9.
    min_abs: keep values with abs(x) >= min_abs (mimics a '> 1' filter). Use None to include sub-1 values.
    Returns (total_count, counts[1..9], percentages[1..9]).
    """
    s = series.dropna().astype(float)
    if min_abs is not None:
        s = s[abs(s) >= float(min_abs)]

    digits = []
    for val in s:
        d = leading_digit(val)
        if d is not None:
            digits.append(d)

    counts = [digits.count(d) for d in range(1, 10)]
    total = int(sum(counts))
    pct = [(c * 100.0 / total) if total else 0.0 for c in counts]
    return total, counts, pct


def expected_counts(total: int) -> List[int]:
    """Expected counts per Benford given total sample size."""
    return [round(p * total / 100.0) for p in BENFORD_PCT]


def chi_square_test(observed: List[int], expected: List[int]) -> float:
    """Return chi-square statistic for observed vs expected (1..9 bins)."""
    chi2 = 0.0
    for o, e in zip(observed, expected):
        if e == 0:
            continue
        chi2 += (o - e) ** 2 / e
    return float(chi2)


# ---------------- Plots ----------------
def bar_chart_percent(observed_pct: List[float]) -> None:
    """Bar chart of observed % with Benford % as overlay points."""
    x = [i for i in range(1, 10)]
    fig, ax = plt.subplots()
    try:
        fig.canvas.manager.set_window_title("Percentage First Digits")
    except Exception:
        pass

    ax.set_title("Data vs Benford (Leading Digit %)", fontsize=15)
    ax.set_ylabel("Frequency (%)", fontsize=12)
    ax.set_xticks(x, x)

    bars = ax.bar(x, observed_pct, width=0.95, label="Data")
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h, f"{h:.1f}", ha="center", va="bottom", fontsize=10)

    ax.scatter(x, BENFORD_PCT, s=100, zorder=3, label="Benford")
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    plt.show()


def bar_chart_side_by_side(observed_pct: List[float]) -> None:
    """Side-by-side bars: observed vs Benford (in %)."""
    x = np.arange(1, 10)
    width = 0.4
    fig, ax = plt.subplots()
    ax.bar(x - width / 2, observed_pct, width, label="Data")
    ax.bar(x + width / 2, BENFORD_PCT, width, label="Benford")
    ax.set_title("Benford – Observed vs Expected (%)")
    ax.set_ylabel("Frequency (%)")
    ax.set_xticks(x, x)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    plt.show()


# ---------------- Popup helper ----------------
def show_decision_popup(chi2_stat: float, crit: float, consistent: bool, p_value: Optional[float]) -> None:
    """Show a popup summarizing the chi-square decision rule and this run's verdict."""
    title = "Benford Decision"
    verdict = "✅ CONSISTENT with Benford at 5%" if consistent else "❌ NOT consistent with Benford at 5%"
    body = (
        f"Chi-squared Test Statistic = {chi2_stat:.3f}\n"
        f"Critical value (8 d.f., α=0.05) = {crit:.3f}\n"
        f"{'(p-value = ' + f'{p_value:.4f}' + ')' if p_value is not None else ''}\n\n"
        f"Rule:\n"
        f"• If χ² < {crit:.3f}, your data are consistent with Benford at the 5% level (i.e., “obey” Benford).\n"
        f"• If χ² ≥ {crit:.3f}, they are not.\n\n"
        f"Verdict: {verdict}"
    )
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, body)
        root.destroy()
    except Exception:
        print(f"\n[{title}]\n{body}\n")


# ---------------- Orchestration ----------------
def run_benford(filename: Union[str, Path], column: str,
                min_abs: Optional[float] = 1.0, show_both_charts: bool = False) -> None:
    """
    Execute Benford analysis on an Excel file & numeric column.
    min_abs: set to 1.0 to mimic a '>1' filter; set to None to include sub-1 values.
    """
    s = load_data(filename, column)

    # Quick exploration (printed)
    print("\n--- Data snapshot ---")
    print(pd.DataFrame({column: s}).describe().T)

    total, obs_counts, obs_pct = count_first_digit(s, min_abs=min_abs)
    if total == 0:
        show_decision_popup(float("nan"), CHI2_CRIT_8DF_0_05, False, None)
        print("\nNo usable values after filtering (check the column name and min_abs filter).")
        return

    exp_counts = expected_counts(total)
    chi2 = chi_square_test(obs_counts, exp_counts)
    consistent = chi2 < CHI2_CRIT_8DF_0_05

    # Optional p-value (SciPy if available)
    p_value = None
    try:
        from scipy.stats import chi2 as chi2_dist  # optional
        p_value = float(1 - chi2_dist.cdf(chi2, df=8))
    except Exception:
        pass

    print("\nObserved counts: ", obs_counts)
    print("Expected counts: ", exp_counts)
    print(f"\nChi-squared Test Statistic = {chi2:.3f}")
    print(f"Critical value (8 d.f., α=0.05) = {CHI2_CRIT_8DF_0_05:.3f}")
    if p_value is not None:
        print(f"p-value = {p_value:.4f}")
    print("Decision:", "Benford-consistent ✅" if consistent else "Not Benford-consistent ❌")

    print("\nFirst Digit Probabilities (observed vs Benford):")
    for d in range(1, 10):
        print(f"{d}: observed={obs_pct[d-1]/100:.3f} expected={BENFORD_PCT[d-1]/100:.3f}")

    # Plots
    bar_chart_percent(obs_pct)
    if show_both_charts:
        bar_chart_side_by_side(obs_pct)

    # Popup with the rule + verdict
    show_decision_popup(chi2, CHI2_CRIT_8DF_0_05, consistent, p_value)


# ---------------- Interactive launcher ----------------
def _interactive_launch():
    """Ask for file, column, filter & options, then run analysis."""
    try:
        import tkinter as tk
        from tkinter import filedialog, simpledialog, messagebox
    except Exception:
        print("Tkinter not available; please call run_benford(file, column, ...) directly.")
        return

    root = tk.Tk()
    root.withdraw()

    filename = filedialog.askopenfilename(
        title="Select Excel file",
        filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
    )
    if not filename:
        messagebox.showinfo("Benford", "No file selected. Exiting.")
        root.destroy()
        return

    # Peek columns to help the user pick
    try:
        df_preview = pd.read_excel(filename, nrows=50)
        cols_list = ", ".join(map(str, df_preview.columns.tolist()))
    except Exception as e:
        messagebox.showerror("Error", f"Could not read the file:\n{e}")
        root.destroy()
        return

    col = simpledialog.askstring(
        "Select Column",
        f"Enter the column name to analyze.\n\nAvailable columns:\n{cols_list}",
        parent=root,
        initialvalue="Amount" if "Amount" in df_preview.columns else None
    )
    if not col:
        messagebox.showinfo("Benford", "No column provided. Exiting.")
        root.destroy()
        return

    min_abs_str = simpledialog.askstring(
        "Minimum absolute value filter",
        "Keep values with |x| >= this.\nEnter a number, or 'none' to include all.\n(Default: 1.0)",
        parent=root,
        initialvalue="1.0"
    )
    if min_abs_str is None:
        messagebox.showinfo("Benford", "Canceled. Exiting.")
        root.destroy()
        return
    min_abs = None if str(min_abs_str).strip().lower() == "none" else float(min_abs_str)

    show_both = messagebox.askyesno("Charts", "Show both charts (side-by-side and overlay)?")

    root.destroy()
    run_benford(filename, col, min_abs=min_abs, show_both_charts=show_both)


# ---------------- Main ----------------
if __name__ == "__main__":
    # 1) If your dummy file exists, auto-run it for convenience:
    default = Path("mydata.xlsx")
    if default.exists():
        try:
            run_benford(default, "Amount", min_abs=1.0, show_both_charts=True)
            sys.exit(0)
        except Exception:
            pass

    # 2) If arguments are provided: python benford.py file.xlsx Column -- optional
    if len(sys.argv) >= 3:
        file_arg = sys.argv[1]
        col_arg = sys.argv[2]
        # Optional: third arg for min_abs
        min_abs_arg = None
        if len(sys.argv) >= 4:
            if sys.argv[3].lower() != "none":
                min_abs_arg = float(sys.argv[3])
        run_benford(file_arg, col_arg, min_abs=min_abs_arg, show_both_charts=True)
    else:
        # 3) Interactive picker
        _interactive_launch()


