'''
Created on 14 Mar 2023

@author: T-RexPO
'''
import math
import pandas as pd
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import os

# ----------------------------
# Benford's Law constants
# ----------------------------
BENFORD = [30.1, 17.6, 12.5, 9.7, 7.9, 6.7, 5.8, 5.1, 4.6]  # % for digits 1..9
CHI2_CRIT_8DF_0_05 = 15.507  # critical chi-square value (df=8, alpha=0.05)


# ----------------------------
# Data loading
# ----------------------------
def load_data(filename: str, var: str):
    """Load Excel or CSV and return (df, series) for column 'var'."""
    ext = os.path.splitext(filename)[1].lower()

    if ext in [".xls", ".xlsx"]:
        df = pd.read_excel(filename)
    elif ext == ".csv":
        df = pd.read_csv(filename)
    else:
        raise ValueError("Unsupported file type. Please select .xls, .xlsx, or .csv")

    if var not in df.columns:
        raise ValueError(f"Column '{var}' not found. Available columns: {list(df.columns)}")
    data = df[var]
    return df, data


# ----------------------------
# Helpers for leading digit
# ----------------------------
def leading_digit(x):
    """Return the leading digit 1..9 for a numeric value, or None if not applicable."""
    try:
        x = float(x)
    except Exception:
        return None
    if not math.isfinite(x):
        return None
    x = abs(x)
    if x == 0:
        return None
    while x >= 10:
        x /= 10.0
    while x < 1:
        x *= 10.0
    d = int(x)
    return d if 1 <= d <= 9 else None


# ----------------------------
# Counting / percentages
# ----------------------------
def count_first_digit(df: pd.DataFrame, col_name: str):
    """Compute counts/percentages for first digits 1..9 from df[col_name]."""
    s_num = pd.to_numeric(df[col_name], errors="coerce").dropna()
    s_num = s_num[s_num > 1]

    counts = [0] * 9
    for val in s_num:
        d = leading_digit(val)
        if d is not None:
            counts[d - 1] += 1

    total = sum(counts)
    pct = [(c * 100.0 / total) if total else 0.0 for c in counts]
    return total, counts, pct


# ----------------------------
# Expected counts
# ----------------------------
def get_expected_counts(total_count: int):
    """Return expected Benford counts for digits 1..9 given total sample size."""
    return [round(p * total_count / 100.0) for p in BENFORD]


# ----------------------------
# Chi-square test
# ----------------------------
def chi_square_test(observed_counts, expected_counts):
    """Chi-square test (8 d.f., α=0.05). Returns (chi2_stat, consistent_bool)."""
    chi2 = 0.0
    for obs, exp in zip(observed_counts, expected_counts):
        if exp == 0:
            continue
        chi2 += (obs - exp) ** 2 / exp
    return chi2, (chi2 < CHI2_CRIT_8DF_0_05)


# ----------------------------
# Explanation helper
# ----------------------------
def top_deviations(observed_pct, k=3):
    """Return a list of the k largest deviations from Benford in percentage points."""
    diffs = []
    for d in range(1, 10):
        obs = observed_pct[d - 1]
        exp = BENFORD[d - 1]
        diffs.append((d, obs, exp, obs - exp))
    diffs.sort(key=lambda t: abs(t[3]), reverse=True)
    lines = []
    for d, obs, exp, delta in diffs[:k]:
        sign = "+" if delta >= 0 else "−"
        lines.append(f"Digit {d}: observed {obs:.1f}% vs expected {exp:.1f}% ({sign}{abs(delta):.1f} pp)")
    return lines


# ----------------------------
# Plotting
# ----------------------------
def bar_chart(observed_pct):
    """Bar chart of observed % vs Benford % (digits 1..9)."""
    index = list(range(1, 10))
    fig, ax = plt.subplots()
    try:
        fig.canvas.manager.set_window_title("Percentage First Digits")
    except Exception:
        pass

    ax.set_title("Data vs. Benford Values", fontsize=15)
    ax.set_ylabel("Frequency (%)", fontsize=16)
    ax.set_xticks(index)
    ax.set_xticklabels(index, fontsize=14)

    rects = ax.bar(index, observed_pct, width=0.95, color="black", label="Data")
    for rect in rects:
        h = rect.get_height()
        ax.text(rect.get_x() + rect.get_width() / 2, h,
                f"{h:.1f}", ha="center", va="bottom", fontsize=13)

    ax.scatter(index, BENFORD, s=150, c="red", zorder=2, label="Benford")
    ax.legend(prop={"size": 14}, frameon=False)
    fig.tight_layout()
    plt.show()


# ----------------------------
# Input dialogs
# ----------------------------
def get_user_inputs():
    """Show popups to get Excel or CSV filepath and column name."""
    root = tk.Tk()
    root.withdraw()

    filepath = filedialog.askopenfilename(
        title="Select Excel or CSV file for Benford analysis",
        filetypes=[("Data files", "*.xlsx *.xls *.csv"), ("All files", "*.*")]
    )
    if not filepath:
        messagebox.showinfo("Benford Analysis", "No file selected. Exiting.")
        root.destroy()
        return None, None

    column = simpledialog.askstring(
        "Column Name",
        "Enter the column name to analyze (numeric values, filter > 1):",
        parent=root
    )
    if not column:
        messagebox.showinfo("Benford Analysis", "No column name provided. Exiting.")
        root.destroy()
        return None, None

    root.destroy()
    return filepath, column


# ----------------------------
# Main
# ----------------------------
def main():
    filepath, column = get_user_inputs()
    if not filepath or not column:
        return

    try:
        df, data = load_data(filepath, column)
    except Exception as e:
        tk.Tk().withdraw()
        messagebox.showerror("Load Error", f"Could not load data:\n{e}")
        return

    total_count, data_count, data_percentage = count_first_digit(df, column)
    expected_counts = get_expected_counts(total_count)
    chi2, consistent = chi_square_test(data_count, expected_counts)

    # 5) Popup summary (green/red)
    root_popup = tk.Tk()
    root_popup.withdraw()

    if total_count == 0:
        messagebox.showwarning(
            "Benford Summary",
            "No valid values (> 1) found in the selected column.\n"
            "Please check the data or choose a different column."
        )
        root_popup.destroy()
        return

    popup = tk.Toplevel()
    popup.title("Benford Summary")

    if consistent:
        bg_color = "#b6f7b0"  # light green
        msg = (
            "✅ Your data are consistent with Benford's Law at the 5% level.\n\n"
            f"χ² = {chi2:.3f} < {CHI2_CRIT_8DF_0_05:.3f}\n"
            f"Sample size used (after >1 filter): {total_count}"
        )
    else:
        bg_color = "#ffcccc"  # light red
        reasons = "\n".join(top_deviations(data_percentage, k=3))
        msg = (
            "❌ Your data do NOT appear to follow Benford's Law at the 5% level.\n\n"
            f"χ² = {chi2:.3f} ≥ {CHI2_CRIT_8DF_0_05:.3f}\n"
            f"Sample size used (after >1 filter): {total_count}\n\n"
            "Largest deviations:\n" + reasons
        )

    popup.configure(bg=bg_color)
    popup.geometry("480x300")

    label = tk.Label(
        popup, text=msg, bg=bg_color,
        font=("Segoe UI", 11), justify="left", wraplength=440
    )
    label.pack(padx=15, pady=15, fill="both", expand=True)

    tk.Button(
        popup, text="OK", command=popup.destroy,
        font=("Segoe UI", 11), width=10
    ).pack(pady=(0, 15))

    popup.grab_set()
    root_popup.mainloop()

    # 6) Console summary
    print("\nTotal counted (after >1 filter):", total_count)
    print("Observed counts:", data_count)
    print("Observed %:", [round(x, 2) for x in data_percentage])
    print("Expected counts (Benford):", expected_counts)
    print(f"Chi² = {chi2:.3f} | Critical (0.05, df=8) = {CHI2_CRIT_8DF_0_05:.3f}")
    print("Decision:", "Consistent ✅" if consistent else "Not consistent ❌")

    # 7) Plot
    bar_chart(data_percentage)


if __name__ == "__main__":
    main()










