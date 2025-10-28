'''
Created on 9 Oct 2025

@author: T-RexPO
'''
# popup_motivation.py
import tkinter as tk
from tkinter import Toplevel, Label, PhotoImage
from playsound import playsound
import os, sys, threading

base = os.path.dirname(os.path.abspath(sys.argv[0]))
img = os.path.join(base, "tony1.png")
sound = os.path.join(base, "applause.wav")

def play_sound():
    if os.path.exists(sound):
        threading.Thread(target=lambda: playsound(sound), daemon=True).start()

play_sound()

root = tk.Tk()
root.withdraw()
popup = Toplevel(root)
popup.title("Motivation")
popup.geometry("400x300")
popup.configure(bg="white")

img_label = Label(popup, image=PhotoImage(file=img), bg="white")
img_label.image = PhotoImage(file=img)
img_label.pack(pady=10)

Label(popup, text="You're doing a good job...", font=("Arial", 14, "bold"),
      bg="white", fg="darkgreen").pack(pady=10)

popup.after(5000, popup.destroy)
root.after(5500, root.destroy)
root.mainloop()
