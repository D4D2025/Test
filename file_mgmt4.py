'''
Created on 20 Sep 2025

@author: hp
'''
import os
import shutil
import subprocess
import platform
import time
from pathlib import Path
from typing import List, Optional
from reportlab.platypus import Paragraph
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd


# ---------------- Theme ----------------
EXCEL_GREEN = "#217346"  # Excel brand green
EXCEL_WHITE = "white"
FLASH_GREEN = "#00C853"  # Green flash for success
FLASH_YELLOW = "#FFEB3B"  # Yellow "Done!" label background

# use for fallback fonts i.e provide a list of secondary fonts should the first font not render:-
# e.g. add the following as the third parameter: [("Bauhaus", "C:\\Windows\\Fonts\\BAUHS93.TTF"), ("Arial", "C:\\Windows\\Fonts\\arial.ttf")]
class MultiFontParagraph(Paragraph):
    # Created by B8Vrede for http://stackoverflow.com/questions/35172207/
    def __init__(self, text, style, fonts_locations):

        font_list = []
        for font_name, font_location in fonts_locations:
            # Load the font
            font = TTFont(font_name, font_location)

            # Get the char width of all known symbols
            font_widths = font.face.charWidths

            # Register the font to able it use
            pdfmetrics.registerFont(font)

            # Store the font and info in a list for lookup
            font_list.append((font_name, font_widths))

        # Set up the string to hold the new text
        new_text = u''

        # Loop through the string
        for char in text:

            # Loop through the fonts
            for font_name, font_widths in font_list:

                # Check whether this font know the width of the character
                # If so it has a Glyph for it so use it
                if ord(char) in font_widths:

                    # Set the working font for the current character
                    new_text += u'<font name="{}">{}</font>'.format(font_name, char)
                    break

        Paragraph.__init__(self, new_text, style)

# ---------- Collapsible Frame ----------
class CollapsibleFrame(tk.Frame):
    """A collapsible frame with a toggle button."""
    def __init__(self, master, text="", collapsed=False, *args, **kwargs):
        super().__init__(master, *args, **kwargs, bg=EXCEL_GREEN)
        self.is_collapsed = tk.BooleanVar(value=collapsed)

        self.header = tk.Frame(self, bg=EXCEL_GREEN)
        self.header.pack(fill="x", pady=1)

        self.toggle_btn = tk.Button(
            self.header, width=2, text="-" if not collapsed else "+",
            command=self.toggle, bg=EXCEL_GREEN, fg=EXCEL_WHITE,
            activebackground=EXCEL_GREEN, activeforeground=EXCEL_WHITE, relief="raised"
        )
        self.toggle_btn.pack(side="left")

        tk.Label(self.header, text=text, font=("Arial", 9, "bold"),
                 bg=EXCEL_GREEN, fg=EXCEL_WHITE).pack(side="left", padx=4)

        self.content = tk.Frame(self, bg=EXCEL_GREEN)
        if not collapsed:
            self.content.pack(fill="x", expand=True)

    def toggle(self):
        if self.is_collapsed.get():
            self.content.pack(fill="x", expand=True)
            self.toggle_btn.config(text="-")
            self.is_collapsed.set(False)
        else:
            self.content.pack_forget()
            self.toggle_btn.config(text="+")
            self.is_collapsed.set(True)


# ---------- Pane ----------
class Pane:
    """One side of the dual-pane file manager (with collapsible sections)."""
    def __init__(self, master, title: str):
        self.frame = tk.Frame(master, relief="groove", borderwidth=2, bg=EXCEL_GREEN)
        self.frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.title = title
        self.directory: Optional[Path] = None
        self.current_items: List[str] = []
        self.last_command = None

        # Auto-refresh
        self.auto_refresh_enabled = tk.BooleanVar(value=False)
        self.refresh_interval = tk.IntVar(value=5)

        # Header
        tk.Label(self.frame, text=title, font=("Arial", 10, "bold"),
                 bg=EXCEL_GREEN, fg=EXCEL_WHITE).pack()

        # ---- Commands (collapsible) — start collapsed
        self.commands_cf = CollapsibleFrame(self.frame, text="Commands", collapsed=True)
        self.commands_cf.pack(fill="x", pady=2)
        self.cmd_frame = self.commands_cf.content

        # Order: All → Folders → Files → *.py → *.ipynb → A→Z → By Size
        for label, fn in [
            ("All", self.list_all),
            ("Folders", self.list_folders),
            ("Files", self.list_files),
            ("*.py", self.list_python_files),
            ("*.ipynb", self.list_notebooks),
            ("A→Z", self.sort_files_alpha),
            ("By Size", self.sort_files_size),
        ]:
            tk.Button(self.cmd_frame, text=label,
                      command=lambda f=fn: self.run_command(f),
                      bg=EXCEL_GREEN, fg=EXCEL_WHITE,
                      activebackground=EXCEL_GREEN, activeforeground=EXCEL_WHITE
                      ).pack(side="left", padx=2, pady=1)

        # ↑ Up button (in Commands)
        tk.Button(self.cmd_frame, text="↑ Up",
                  command=self.go_up,
                  bg=EXCEL_GREEN, fg=EXCEL_WHITE).pack(side="left", padx=6)

        # ---- Directory chooser
        tk.Button(self.frame, text="Select Directory", command=self.ask_directory,
                  bg=EXCEL_GREEN, fg=EXCEL_WHITE).pack(pady=2)

        # ---- Search (collapsible) — start collapsed
        self.search_cf = CollapsibleFrame(self.frame, text="Search / Filter", collapsed=True)
        self.search_cf.pack(fill="x", pady=2)
        tk.Label(self.search_cf.content, text="Enter text:",
                 bg=EXCEL_GREEN, fg=EXCEL_WHITE).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.apply_filter)
        self.search_entry = tk.Entry(self.search_cf.content, textvariable=self.search_var,
                                     width=30, bg="white", fg="black")
        self.search_entry.pack(side="left", padx=4)

        # ---- Progress bar (with percentage label + flash "Done!")
        # Prepare ttk styles for default and green flash
        self.style = ttk.Style(self.frame)
        # Create a unique base style per pane to avoid clashes
        self.base_style = f"{self.title}.Horizontal.TProgressbar"
        self.flash_style = f"{self.title}.Green.Horizontal.TProgressbar"

        # Base style (keep default look; troughcolor only if supported)
        try:
            self.style.configure(self.base_style, troughcolor="#E0E0E0")
        except Exception:
            pass  # some themes ignore this

        # Green flash style
        try:
            # 'background' usually sets the bar color (theme-dependent)
            self.style.configure(self.flash_style, background=FLASH_GREEN)
        except Exception:
            pass

        self.progress = ttk.Progressbar(self.frame, orient="horizontal",
                                        mode="determinate", length=200,
                                        style=self.base_style)
        self.progress.pack(pady=(2, 0))

        # Percentage label under the progress bar
        self.progress_pct_var = tk.StringVar(value="0%")
        self.progress_pct_label = tk.Label(self.frame, textvariable=self.progress_pct_var,
                                           bg=EXCEL_GREEN, fg=EXCEL_WHITE, font=("Arial", 9))
        self.progress_pct_label.pack(pady=(0, 4))

        # Hidden "Done!" flash label (shown briefly after copy/move)
        self.done_label = tk.Label(self.frame, text="Done!", bg=FLASH_YELLOW, fg="black",
                                   font=("Arial", 9, "bold"))
        # not packed initially

        # ---- Auto-refresh (collapsible) — start collapsed
        self.refresh_cf = CollapsibleFrame(self.frame, text="Auto-refresh", collapsed=True)
        self.refresh_cf.pack(fill="x", pady=2)
        tk.Checkbutton(self.refresh_cf.content, text="Enable",
                       variable=self.auto_refresh_enabled,
                       bg=EXCEL_GREEN, fg=EXCEL_WHITE, selectcolor=EXCEL_GREEN).pack(side="left")
        tk.Label(self.refresh_cf.content, text="Interval (s):",
                 bg=EXCEL_GREEN, fg=EXCEL_WHITE).pack(side="left", padx=5)
        tk.Entry(self.refresh_cf.content, textvariable=self.refresh_interval,
                 width=5, bg="white", fg="black").pack(side="left")

        # ---- Listbox with vertical + horizontal scrollbars ----
        listbox_frame = tk.Frame(self.frame, bg=EXCEL_GREEN)
        listbox_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Create scrollbars
        self.v_scroll = tk.Scrollbar(listbox_frame, orient="vertical")
        self.h_scroll = tk.Scrollbar(listbox_frame, orient="horizontal")

        # Create listbox with scroll commands
        self.listbox = tk.Listbox(
            listbox_frame,
            width=60, height=20, selectmode="extended",
            bg="white", fg="black",
            selectbackground=EXCEL_GREEN, selectforeground=EXCEL_WHITE,
            yscrollcommand=self.v_scroll.set,
            xscrollcommand=self.h_scroll.set
        )

        # Configure scrollbars to control the listbox
        self.v_scroll.config(command=self.listbox.yview)
        self.h_scroll.config(command=self.listbox.xview)

        # Layout: vertical on the right, horizontal at the bottom
        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.listbox.pack(side="left", fill="both", expand=True)

        # Bind double-click to open folder
        self.listbox.bind("<Double-1>", self._on_double_click)

        # Context menu
        self.context_menu = tk.Menu(self.frame, tearoff=0,
                                    bg=EXCEL_GREEN, fg=EXCEL_WHITE,
                                    activebackground="#1b5e3e", activeforeground=EXCEL_WHITE)
        self.context_menu.add_command(label="Open", command=self.open_selected)
        self.context_menu.add_command(label="Delete", command=self.delete_selected_with_confirm)
        self.context_menu.add_command(label="Properties", command=self.show_properties_selected)
        self.listbox.bind("<Button-3>", self._right_click_select_then_menu)

        # ---- Export (collapsible) — start collapsed
        self.export_cf = CollapsibleFrame(self.frame, text="Export/Clear/Delete", collapsed=True)
        self.export_cf.pack(fill="x", pady=2)
        tk.Button(self.export_cf.content, text="CSV", command=self.export_csv,
                  bg=EXCEL_GREEN, fg=EXCEL_WHITE).pack(side="left", padx=2)
        tk.Button(self.export_cf.content, text="Excel", command=self.export_excel,
                  bg=EXCEL_GREEN, fg=EXCEL_WHITE).pack(side="left", padx=2)
        tk.Button(self.export_cf.content, text="PDF", command=self.export_pdf,
                  bg=EXCEL_GREEN, fg=EXCEL_WHITE).pack(side="left", padx=2)
        tk.Button(self.export_cf.content, text="Clear",
                  command=self.clear_pane,
                  bg=EXCEL_GREEN, fg="yellow").pack(side="left", padx=10)
        tk.Button(self.export_cf.content, text="Delete",
                  command=self.delete_selected_with_confirm,
                  bg=EXCEL_GREEN, fg="red").pack(side="left", padx=2)

        # Inline "Done!" label for exports (not packed initially)
        self.export_done_label = tk.Label(self.export_cf.content, text="Done!",
                                          bg=FLASH_YELLOW, fg="black",
                                          font=("Arial", 9, "bold"))

        # ---- Status bar
        self.status_label = tk.Label(self.frame, text="No directory selected",
                                     anchor="w", relief="sunken",
                                     bg=EXCEL_GREEN, fg=EXCEL_WHITE)
        self.status_label.pack(fill="x", side="bottom")

        # Schedule auto-refresh
        self.frame.after(1000, self._schedule_auto_refresh)

    # ------------------------------
    # Progress helpers (percentage + flash)
    # ------------------------------
    def _set_progress(self, value: float, maximum: float):
        self.progress["maximum"] = max(1, maximum)
        self.progress["value"] = max(0, min(value, self.progress["maximum"]))
        try:
            pct = int(round((self.progress["value"] / self.progress["maximum"]) * 100))
        except Exception:
            pct = 0
        self.progress_pct_var.set(f"{pct}%")
        self.frame.update_idletasks()

    def _reset_progress(self):
        self._set_progress(0, self.progress["maximum"])

    def flash_success(self, duration_ms: int = 1500):
        """Show 'Done!' in yellow and flash the bar green briefly, then reset."""
        # Show "Done!" (under the percent label)
        try:
            # If already packed, don't duplicate
            if not self.done_label.winfo_ismapped():
                self.done_label.pack(pady=(0, 6))
        except Exception:
            pass

        # Switch to green style (if supported)
        try:
            self.progress.configure(style=self.flash_style)
        except Exception:
            pass

        # After duration, hide label, revert style, and reset progress/percent
        def _end_flash():
            try:
                if self.done_label.winfo_ismapped():
                    self.done_label.pack_forget()
            except Exception:
                pass
            try:
                self.progress.configure(style=self.base_style)
            except Exception:
                pass
            self._reset_progress()

        self.frame.after(duration_ms, _end_flash)

    def flash_export_done(self, duration_ms: int = 1500):
        """Show 'Done!' label in the Export row temporarily."""
        try:
            if not self.export_done_label.winfo_ismapped():
                self.export_done_label.pack(side="left", padx=6)
        except Exception:
            pass

        def _hide():
            try:
                if self.export_done_label.winfo_ismapped():
                    self.export_done_label.pack_forget()
            except Exception:
                pass

        self.frame.after(duration_ms, _hide)

    # ------------------------------
    # Commands (buttons)
    # ------------------------------
    def list_all(self):
        """Show all folders and files (folders dark blue + '/' suffix)."""
        if not self.directory:
            return
        try:
            dirs = []
            files = []
            with os.scandir(self.directory) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            dirs.append(e.name + "/")   # mark folders with '/'
                        else:
                            files.append(e.name)
                    except PermissionError:
                        continue
            items = sorted(dirs, key=str.lower) + sorted(files, key=str.lower)
        except Exception as e:
            messagebox.showerror("List All", f"Couldn't read directory:\n{e}")
            items = []
        self.update_list_with_progress(items, show_folders=True)

    def list_contents(self):
        """Default listing."""
        self.list_all()

    def list_files(self):
        """Show only files (no folders)."""
        if not self.directory:
            return
        try:
            items = []
            with os.scandir(self.directory) as it:
                for e in it:
                    try:
                        if not e.is_dir(follow_symlinks=False):
                            items.append(e.name)
                    except PermissionError:
                        continue
            items.sort(key=str.lower)
        except Exception as e:
            messagebox.showerror("List Files", f"Couldn't read directory:\n{e}")
            items = []
        self.update_list_with_progress(items, show_folders=False)

    def list_folders(self):
        """Show only folders (no files)."""
        if not self.directory:
            return
        try:
            items = []
            with os.scandir(self.directory) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            items.append(e.name + "/")  # mark folders
                    except PermissionError:
                        continue
            items.sort(key=str.lower)
        except Exception as e:
            messagebox.showerror("List Folders", f"Couldn't read directory:\n{e}")
            items = []
        self.update_list_with_progress(items, show_folders=True)

    def list_python_files(self):
        if self.directory:
            try:
                items = [f.name for f in self.directory.glob("*.py")]
            except Exception as e:
                messagebox.showerror("*.py", f"Couldn't read directory:\n{e}")
                items = []
            self.update_list_with_progress(sorted(items, key=str.lower), show_folders=False)

    def list_notebooks(self):
        if self.directory:
            try:
                items = [f.name for f in self.directory.glob("*.ipynb")]
            except Exception as e:
                messagebox.showerror("*.ipynb", f"Couldn't read directory:\n{e}")
                items = []
            self.update_list_with_progress(sorted(items, key=str.lower), show_folders=False)

    def sort_files_alpha(self):
        if self.directory:
            try:
                items = sorted([f.name for f in self.directory.iterdir() if f.is_file()], key=lambda x: x.lower())
            except Exception as e:
                messagebox.showerror("Sort A→Z", f"Couldn't read directory:\n{e}")
                items = []
            self.update_list_with_progress(items, show_folders=False)

    def sort_files_size(self):
        if self.directory:
            try:
                files = [f for f in self.directory.iterdir() if f.is_file()]
                files.sort(key=lambda x: x.stat().st_size)
                items = [f"{f.name} - {f.stat().st_size} bytes" for f in files]
            except Exception as e:
                messagebox.showerror("By Size", f"Couldn't read directory:\n{e}")
                items = []
            self.update_list_with_progress(items, show_folders=False)

    # ------------------------------
    # Navigation helpers
    # ------------------------------
    def go_up(self):
        """Go up one directory (reverse the last 'open folder' action)."""
        if not self.directory:
            self.frame.bell()
            return
        parent = self.directory.parent
        if parent == self.directory:
            self.frame.bell()
            return
        self.directory = parent.resolve()
        self.list_contents()
        self.last_command = self.list_contents

    # ------------------------------
    # Auto-refresh
    # ------------------------------
    def _schedule_auto_refresh(self):
        if self.auto_refresh_enabled.get() and self.last_command:
            try:
                self.last_command()
            except Exception:
                pass
        try:
            interval_ms = max(1, int(self.refresh_interval.get())) * 1000
        except Exception:
            interval_ms = 5000
        self.frame.after(interval_ms, self._schedule_auto_refresh)

    # ------------------------------
    # Helpers
    # ------------------------------
    def run_command(self, cmd):
        self.last_command = cmd
        cmd()

    def _reset_list(self):
        self.listbox.delete(0, tk.END)

    def _parse_entry_to_name(self, entry: str) -> str:
        # Handle trailing "/" for directories
        name = entry.rstrip("/")

        # Handle " - N bytes" only if it really looks like a size suffix
        if " - " in name and name.split(" - ")[-1].strip().endswith("bytes"):
            name = " - ".join(name.split(" - ")[:-1])

        return name


    def _colorize_item(self, idx, item: str, show_folders: bool):
        """Apply per-row styling (folders dark blue; known file types colored)."""
        if not self.directory:
            return
        name_only = self._parse_entry_to_name(item)
        path = (self.directory / name_only)
        try:
            is_dir = path.is_dir()
        except Exception:
            is_dir = item.endswith("/")  # fallback to marker

        if show_folders and (is_dir or item.endswith("/")):
            self.listbox.itemconfig(idx, fg="darkblue")
        elif name_only.lower().endswith(".py"):
            self.listbox.itemconfig(idx, fg="green")
        elif name_only.lower().endswith(".ipynb"):
            self.listbox.itemconfig(idx, fg="blue")
        elif name_only.lower().endswith(".pdf"):
            self.listbox.itemconfig(idx, fg="deeppink")
        elif name_only.lower().endswith((".xls", ".xlsx", ".csv")):
            self.listbox.itemconfig(idx, fg="darkgoldenrod")
        elif name_only.lower().endswith((".txt", ".md", ".rtf", ".log")):
            self.listbox.itemconfig(idx, fg="purple")
        else:
            self.listbox.itemconfig(idx, fg="black")

    def update_list_with_progress(self, items: List[str], show_folders: bool = False):
        """Insert items and apply per-row styling."""
        self._reset_list()
        total = len(items)
        self._set_progress(0, max(1, total))
        for i, item in enumerate(items, start=1):
            self.listbox.insert(tk.END, item)
            self._colorize_item(i - 1, item, show_folders)
            self._set_progress(i, max(1, total))
        self.current_items = items
        self._reset_progress()
        self._update_status(len(items))

    def _update_status(self, count: int):
        now = time.strftime("%H:%M:%S")
        if self.directory:
            self.status_label.config(text=f"{self.directory} | Items: {count} | Last refresh: {now}")
        else:
            self.status_label.config(text="No directory selected")

    # ------------------------------
    # Filtering & selection helpers
    # ------------------------------
    def apply_filter(self, *args):
        query = self.search_var.get().lower()
        self._reset_list()
        matches = [item for item in self.current_items if query in item.lower()]
        for idx, item in enumerate(matches):
            self.listbox.insert(tk.END, item)
            # keep folder color when filtering
            self._colorize_item(idx, item, show_folders=True)
        self._update_status(len(matches))

    def ask_directory(self):
        path = filedialog.askdirectory(title=f"Select {self.title} Directory", mustexist=True)
        if path:
            self.directory = Path(path).resolve()
            self.search_var.set("")  # Clear any filter
            self.list_contents()     # Immediately show all contents
            self.last_command = self.list_contents

    def clear_pane(self):
        self.directory = None
        self.search_var.set("")
        self._reset_list()
        self.status_label.config(text="Cleared")

    def get_selected_paths(self) -> List[Path]:
        if not self.directory:
            return []
        indices = self.listbox.curselection()
        names = [self._parse_entry_to_name(self.listbox.get(i)) for i in indices]
        paths: List[Path] = []
        for n in names:
            p = (self.directory / n)
            try:
                if p.exists():
                    paths.append(p)
            except Exception:
                continue
        return paths

    # ------------------------------
    # Folder navigation (double-click)
    # ------------------------------
    def _on_double_click(self, event):
        selection = self.listbox.curselection()
        if not selection or not self.directory:
            return
        name = self._parse_entry_to_name(self.listbox.get(selection[0]))
        path = (self.directory / name)
        try:
            if path.is_dir():
                # 🔑 Set the pane's directory to the newly opened folder
                self.directory = path.resolve()
                self.list_contents()
                self.last_command = self.list_contents
        except Exception as e:
            messagebox.showerror("Open Folder", f"Couldn't open folder:\n{e}")

    # ------------------------------
    # Context menu actions
    # ------------------------------
    def _right_click_select_then_menu(self, event):
        try:
            idx = self.listbox.nearest(event.y)
            if idx not in self.listbox.curselection():
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(idx)
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def open_selected(self):
        for p in self.get_selected_paths():
            try:
                if platform.system() == "Windows":
                    os.startfile(p)  # type: ignore[attr-defined]
                elif platform.system() == "Darwin":
                    subprocess.call(["open", p])
                else:
                    subprocess.call(["xdg-open", p])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open {p.name}: {e}")

    def delete_selected_with_confirm(self):
        paths = self.get_selected_paths()
        if not paths:
            messagebox.showinfo("Delete", "Please select one or more items to delete.")
            return
        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete selected item(s)?"):
            return
        for p in paths:
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete {p.name}: {e}")
        self.list_contents()

    def show_properties_selected(self):
        """Show file/folder properties for the current selection."""
        paths = self.get_selected_paths()
        if not paths:
            messagebox.showinfo("Properties", "Please select one or more items.")
            return

        if len(paths) == 1:
            p = paths[0]
            try:
                size = p.stat().st_size if p.is_file() else 0
                modified = time.ctime(p.stat().st_mtime)
            except Exception:
                size = 0
                modified = "Unknown"
            kind = "Folder" if p.is_dir() else "File"
            props = (
                f"{kind}: {p.name}\n"
                f"Size: {size} bytes\n"
                f"Modified: {modified}\n"
                f"Location: {p.parent}"
            )
            messagebox.showinfo("Properties", props)
        else:
            total_size = 0
            for p in paths:
                try:
                    if p.is_file():
                        total_size += p.stat().st_size
                except Exception:
                    continue
            messagebox.showinfo(
                "Properties (multiple)",
                f"Selected: {len(paths)} items\nTotal file size (files only): {total_size} bytes"
            )

    # ------------------------------
    # Export helpers & actions
    # ------------------------------
    def _get_selected_info(self):
        data = []
        for p in self.get_selected_paths():
            try:
                size = p.stat().st_size if p.is_file() else 0
                modified = time.ctime(p.stat().st_mtime)
            except FileNotFoundError:
                continue
            except Exception:
                size = 0
                modified = "Unknown"
            data.append({
                "Name": p.name,
                "Type": "Folder" if p.is_dir() else "File",
                "Size (bytes)": size,
                "Last Modified": modified,
                "Full Path": str(p.resolve())
            })
        return data

    def export_csv(self):
        data = self._get_selected_info()
        if not data:
            messagebox.showinfo("Export CSV", "Please select one or more items to export.")
            return
        save_path = filedialog.asksaveasfilename(
            title="Save CSV", defaultextension=".csv",
            filetypes=[("CSV UTF-8 (Comma delimited) (*.csv)", "*.csv")]
        )
        if save_path:
            pd.DataFrame(data).to_csv(save_path, index=False, encoding="utf-8-sig")
            self.flash_export_done()

    def export_excel(self):
        data = self._get_selected_info()
        if not data:
            messagebox.showinfo("Export Excel", "Please select one or more items to export.")
            return
        save_path = filedialog.asksaveasfilename(
            title="Save Excel Workbook", defaultextension=".xlsx",
            filetypes=[("Excel Workbook (*.xlsx)", "*.xlsx")]
        )
        if save_path:
            pd.DataFrame(data).to_excel(save_path, index=False)
            self.flash_export_done()

    def export_pdf(self):
        """Export selected items to a PDF with multi-font (Latin, Cyrillic, Greek,
        Chinese, and Hindi/Devanagari) support."""
        data = self._get_selected_info()
        if not data:
            messagebox.showinfo("Export PDF", "Please select one or more items to export.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save PDF", defaultextension=".pdf",
            filetypes=[("PDF (*.pdf)", "*.pdf")]
        )
        if not save_path:
            return

        try:
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, XPreformatted
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        except Exception as e:
            messagebox.showerror("Export PDF", f"ReportLab is required for PDF export:\n{e}")
            return

        # ✅ Register fallback fonts
        font_name = "Helvetica"
        try:
            from pathlib import Path as _P
            ttf = _P(__file__).with_name("DejaVuSans.ttf")
            if ttf.exists():
                pdfmetrics.registerFont(TTFont("DejaVuSans", str(ttf)))
                font_name = "DejaVuSans"
        except Exception:
            pass

        # ✅ Register built-in Chinese font
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        except Exception:
            pass

        # ✅ Windows font registry lookup for Hindi
        import os, sys
        from pathlib import Path
        hindi_font_name = None

        def find_windows_font(font_keywords):
            """Search registry for Windows font by keywords in its display name."""
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
                )
                i = 0
                while True:
                    try:
                        value_name, value, _ = winreg.EnumValue(key, i)
                        if any(kw.lower() in value_name.lower() for kw in font_keywords):
                            font_path = Path(value)
                            if not font_path.is_absolute():
                                font_path = Path("C:/Windows/Fonts") / value
                            if font_path.exists():
                                return str(font_path)
                        i += 1
                    except OSError:
                        break
            except Exception:
                return None
            return None

        if os.name == "nt":  # Windows only
            hindi_path = find_windows_font(["Mangal", "Nirmala"])
            if hindi_path:
                try:
                    pdfmetrics.registerFont(TTFont("HindiFont", hindi_path))
                    hindi_font_name = "HindiFont"
                except Exception:
                    hindi_font_name = None

        # PDF setup
        doc = SimpleDocTemplate(
            save_path,
            pagesize=landscape(A4),
            leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24
        )
        avail_width = doc.width

        styles = getSampleStyleSheet()
        cell_style = ParagraphStyle(
            "Cell",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=8,
            leading=10,
            wordWrap="CJK",
        )
        header_style = ParagraphStyle(
            "Header",
            parent=styles["Heading4"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
        )

        # -------------------------
        # Local helpers
        # -------------------------
        def soft_break(s: str) -> str:
            SOFT = "\u00AD"
            s = str(s)
            s = s.replace("\\", "\\" + SOFT).replace("/", "/" + SOFT)
            for ch in "-_.":
                s = s.replace(ch, ch + SOFT)
            return s

        def contains_chinese(s: str) -> bool:
            return any("\u4e00" <= ch <= "\u9fff" for ch in s)

        def contains_devanagari(s: str) -> bool:
            return any("\u0900" <= ch <= "\u097F" for ch in s)

        # -------------------------
        # Build table data
        # -------------------------
        table_data = [
            [Paragraph("Name", header_style),
             Paragraph("Type", header_style),
             Paragraph("Size (bytes)", header_style),
             Paragraph("Last Modified", header_style),
             Paragraph("Full Path", header_style)]
        ]

        for row in data:
            name = soft_break(row["Name"])
            path = soft_break(row["Full Path"])
            row_texts = [name, row["Type"], str(row["Size (bytes)"]), row["Last Modified"], path]

            row_cells = []
            for txt in row_texts:
                if contains_chinese(txt):
                    row_style = ParagraphStyle("RowCJK", parent=cell_style, fontName="STSong-Light")
                    row_cells.append(Paragraph(txt, row_style))
                elif contains_devanagari(txt) and hindi_font_name:
                    row_style = ParagraphStyle("RowHindi", parent=cell_style, fontName=hindi_font_name)
                    row_cells.append(XPreformatted(txt, row_style))
                else:
                    row_cells.append(
                        MultiFontParagraph(txt, cell_style, [
                            ("Arial", "C:\\Windows\\Fonts\\arial.ttf"),
                            (font_name, "C:\\Windows\\Fonts\\arial.ttf"),
                        ])
                    )
            table_data.append(row_cells)

        # -------------------------
        # Table setup
        # -------------------------
        w_name = 160
        w_type = 60
        w_size = 90
        w_mod  = 130
        w_path = max(120, avail_width - (w_name + w_type + w_size + w_mod))
        col_widths = [w_name, w_type, w_size, w_mod, w_path]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ALIGN",      (0, 0), (-1, -1), "LEFT"),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.black),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ]))

        elements = [
            Paragraph(f"{self.title} Pane — Selected Items", styles["Heading2"]),
            Spacer(1, 10),
            table
        ]

        try:
            doc.build(elements)
            self.flash_export_done()
        except Exception as e:
            messagebox.showerror("Export PDF", f"Could not build PDF:\n{e}")

# ---------- Dual Pane Manager ----------
class DualPaneFileManager:
    def __init__(self, master):
        self.master = master
        self.master.title("Dual-Pane File Manager")
        self.master.configure(bg=EXCEL_GREEN)

        self.left_pane = Pane(master, "Left")
        self.right_pane = Pane(master, "Right")

        # ✅ Only ONE Copy and ONE Move button per pane
        for pane in (self.left_pane, self.right_pane):
            cmd_frame = pane.commands_cf.content
            tk.Button(
                cmd_frame, text="Copy",
                command=lambda p=pane: self.copy_between(p),
                bg=EXCEL_GREEN, fg=EXCEL_WHITE
            ).pack(side="left", padx=6)
            tk.Button(
                cmd_frame, text="Move",
                command=lambda p=pane: self.move_between(p),
                bg=EXCEL_GREEN, fg=EXCEL_WHITE
            ).pack(side="left", padx=6)

        # Window close confirmation
        self.master.protocol("WM_DELETE_WINDOW", self.confirm_exit)
        self.master.bind("<Control-q>", lambda event: self.confirm_exit())

    def confirm_exit(self):
        if messagebox.askyesno("Exit", "Are you sure you want to quit?"):
            self.master.destroy()

    # -------- helpers --------
    def get_opposite(self, pane: Pane) -> Pane:
        return self.right_pane if pane is self.left_pane else self.left_pane

    def copy_between(self, src: Pane):
        dst = self.get_opposite(src)
        self._copy_files(src, dst)

    def move_between(self, src: Pane):
        dst = self.get_opposite(src)
        self._move_files(src, dst)

    # ------------------------------
    # New copy/move logic with folder support
    # ------------------------------
    def _copy_files(self, src: Pane, dst: Pane):
        files = src.get_selected_paths()
        if not files or not dst.directory:
            messagebox.showinfo("Copy", "Select items and set a destination directory in the other pane.")
            return

        # Collect all files inside selected items (folders included)
        all_files = self._collect_all_files(files)
        dst._set_progress(0, len(all_files))

        for i, p in enumerate(all_files, start=1):
            # Compute relative path (preserve folder structure)
            if len(files) == 1 and files[0].is_dir():
                rel_path = p.relative_to(files[0].parent)
            else:
                rel_path = p.name
            target = dst.directory / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)

            # Copy file with chunk progress
            self._copy_with_progress(p, target, dst, i, len(all_files))

        dst._reset_progress()
        dst.list_contents()
        dst.flash_success()

    def _move_files(self, src: Pane, dst: Pane):
        files = src.get_selected_paths()
        if not files or not dst.directory:
            messagebox.showinfo("Move", "Select items and set a destination directory in the other pane.")
            return

        # Collect all files inside selected items (folders included)
        all_files = self._collect_all_files(files)
        dst._set_progress(0, len(all_files))

        for i, p in enumerate(all_files, start=1):
            if len(files) == 1 and files[0].is_dir():
                rel_path = p.relative_to(files[0].parent)
            else:
                rel_path = p.name
            target = dst.directory / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)

            # Copy file first
            self._copy_with_progress(p, target, dst, i, len(all_files))

            # Delete original file
            try:
                p.unlink()
            except Exception as e:
                messagebox.showerror("Move", f"Could not remove {p.name}: {e}")

        dst._reset_progress()
        src.list_contents()
        dst.list_contents()
        dst.flash_success()

    def _copy_with_progress(self, src_path: Path, dst_path: Path, pane: Pane, file_index: int, total_files: int):
        """Copy a single file in chunks and update a 'files overall' progress bar."""
        try:
            total_size = os.path.getsize(src_path)
        except Exception:
            total_size = 0
        copied = 0
        chunk_size = 1024 * 1024  # 1 MB

        with open(src_path, "rb") as src_f, open(dst_path, "wb") as dst_f:
            while True:
                buf = src_f.read(chunk_size)
                if not buf:
                    break
                dst_f.write(buf)
                copied += len(buf)
                if total_size > 0:
                    pane._set_progress((file_index - 1) + (copied / total_size), total_files)
                else:
                    pane._set_progress(file_index - 0.5, total_files)

        try:
            shutil.copystat(src_path, dst_path)
        except Exception:
            pass
        pane._set_progress(file_index, total_files)

    def _collect_all_files(self, paths: List[Path]) -> List[Path]:
        """Recursively collect all files from a list of files/folders."""
        all_files = []
        for p in paths:
            if p.is_file():
                all_files.append(p)
            elif p.is_dir():
                for root, _, files in os.walk(p):
                    for f in files:
                        all_files.append(Path(root) / f)
        return all_files



# ---------- Run ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = DualPaneFileManager(root)
    root.mainloop()