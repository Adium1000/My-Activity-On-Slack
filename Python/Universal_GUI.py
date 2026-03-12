import time
import datetime
import requests
import json
import webbrowser
import threading
import tkinter as tk
import sys
import os
import math
import psutil
from tkinter import messagebox
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from pathlib import Path


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

CONFIG_FILE = get_base_dir() / "spotify_slack_config.json"

def resource_path(relative_path):
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(get_base_dir(), relative_path)

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_config(data):
    try:
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

#Theme
BG        = "#0f0f13"
PANEL     = "#17171f"
CARD      = "#1e1e2a"
CARD2     = "#252533"
BORDER    = "#2a2a3a"
GREEN     = "#1db954"
GREEN_DIM = "#158a3e"
PURPLE    = "#4a3fa0"
PURPLE_LT = "#7c6fcd"
PURPLE_SB = "#5a4fc0"   
TEXT      = "#e8e8f0"
TEXT_DIM  = "#6e6e88"
RED       = "#e05252"
AMBER     = "#e0a832"

FONT_LABEL = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 9)
FONT_BIG   = ("Segoe UI", 11, "bold")

auth_code     = None
access_token  = None
refresh_token = None
running       = False
worker_thread = None

SPOTIFY_REDIRECT_URI = "http://127.0.0.1:9090/callback"
SPOTIFY_SCOPE        = "user-read-currently-playing user-read-playback-state"

DEFAULT_OTHER_APPS = [
    {"process": "Code.exe",   "status_text": "Coding in VS Code",  "emoji": ":vscode:", "description": "Visual Studio Code", "enabled": True},
    {"process": "chrome.exe", "status_text": "Browsing in Chrome", "emoji": ":chrome:", "description": "Google Chrome",      "enabled": True},
]

_app_timers: dict[str, float] = {} 

def fmt_duration(seconds: float) -> str:
    s = int(seconds)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {sec:02d}s"
    return f"{sec}s"

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            auth_code = params["code"][0]
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Authorized! You may close this window.")
    def log_message(self, *_): pass

def get_auth_code(client_id):
    params = {"client_id": client_id, "response_type": "code",
              "redirect_uri": SPOTIFY_REDIRECT_URI, "scope": SPOTIFY_SCOPE}
    webbrowser.open("https://accounts.spotify.com/authorize?" + urlencode(params))
    HTTPServer(("127.0.0.1", 9090), CallbackHandler).handle_request()

def get_tokens(code, client_id, client_secret):
    return requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": SPOTIFY_REDIRECT_URI},
        auth=(client_id, client_secret),
    ).json()

def refresh_access_token_fn(ref_tok, client_id, client_secret):
    return requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "refresh_token", "refresh_token": ref_tok},
        auth=(client_id, client_secret),
    ).json().get("access_token")

def format_ms(ms):
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"

def get_current_track(tok):
    if not tok: return None
    resp = requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers={"Authorization": f"Bearer {tok}"},
    )
    if resp.status_code == 200 and resp.content:
        data = resp.json()
        if data.get("is_playing") and data.get("item"):
            track  = data["item"]["name"]
            artist = data["item"]["artists"][0]["name"]
            return f"{artist} - {track} : {format_ms(data.get('progress_ms',0))}/{format_ms(data['item']['duration_ms'])}"
    return None

def set_slack_status(text, emoji, slack_token):
    if not slack_token: return
    requests.post(
        "https://slack.com/api/users.profile.set",
        headers={"Authorization": f"Bearer {slack_token}", "Content-Type": "application/json"},
        data=json.dumps({"profile": {
            "status_text": text or "", "status_emoji": emoji if text else "", "status_expiration": 0
        }}),
    )

def get_running_processes():
    names = set()
    try:
        for p in psutil.process_iter(["name"]):
            try:
                n = p.info["name"]
                if n: names.add(n)
            except Exception: pass
    except Exception: pass
    return sorted(names, key=lambda x: x.lower())

def draw_rounded_card(cvs, w, h, fill=CARD, outline=BORDER, r=10):
    cvs.delete("all")
    if w < 2*r+1: w = 2*r+1
    if h < 2*r+1: h = 2*r+1
    for x1,y1,x2,y2,st in [
        (0,0,2*r,2*r,90),(w-2*r,0,w,2*r,0),
        (0,h-2*r,2*r,h,180),(w-2*r,h-2*r,w,h,270)]:
        cvs.create_arc(x1,y1,x2,y2,start=st,extent=90,style="pieslice",fill=fill,outline="")
    cvs.create_rectangle(r,0,w-r,h,fill=fill,outline="")
    cvs.create_rectangle(0,r,w,h-r,fill=fill,outline="")
    for x1,y1,x2,y2,st in [
        (0,0,2*r,2*r,90),(w-2*r,0,w,2*r,0),
        (0,h-2*r,2*r,h,180),(w-2*r,h-2*r,w,h,270)]:
        cvs.create_arc(x1,y1,x2,y2,start=st,extent=90,style="arc",outline=outline)
    cvs.create_line(r,0,w-r,0,fill=outline); cvs.create_line(r,h,w-r,h,fill=outline)
    cvs.create_line(0,r,0,h-r,fill=outline); cvs.create_line(w,r,w,h-r,fill=outline)

def make_rounded_btn(parent, text, cmd, color, hover_color,
                     font=None, px=10, py=4, r=6, text_color="white",
                     bg_parent=None):
    """
    Returns a tk.Canvas that looks and behaves like a rounded button.
    Works anywhere without needing an App instance.
    """
    import tkinter.font as tkfont
    if font is None:
        font = ("Segoe UI", 8, "bold")
    f = tkfont.Font(family=font[0], size=font[1],
                    weight=font[2] if len(font) > 2 else "normal")
    bw = f.measure(text) + px * 2
    bh = f.metrics("linespace") + py * 2
    cvs = tk.Canvas(parent, width=bw, height=bh,
                    highlightthickness=0, bd=0,
                    bg=bg_parent or BG, cursor="hand2")
    cvs._color = color
    cvs._hov   = hover_color
    cvs._tcol  = text_color

    def _rd(c=None):
        cvs.delete("all")
        bc = c or cvs._color
        cw, ch = int(cvs["width"]), int(cvs["height"])
        for x1,y1,x2,y2,st in [
            (0,0,2*r,2*r,90),(cw-2*r,0,cw,2*r,0),
            (0,ch-2*r,2*r,ch,180),(cw-2*r,ch-2*r,cw,ch,270)]:
            cvs.create_arc(x1,y1,x2,y2,start=st,extent=90,fill=bc,outline="")
        cvs.create_rectangle(r,0,cw-r,ch,fill=bc,outline="")
        cvs.create_rectangle(0,r,cw,ch-r,fill=bc,outline="")
        cvs.create_text(cw//2, ch//2, text=text, font=font, fill=cvs._tcol)

    cvs._redraw = _rd
    _rd()
    cvs.bind("<Enter>",    lambda _: _rd(cvs._hov))
    cvs.bind("<Leave>",    lambda _: _rd(cvs._color))
    cvs.bind("<Button-1>", lambda _: cmd())
    return cvs

class StatusIndicator(tk.Canvas):
    """
    Modes:
      idle : static dim bars
      eq   : animated EQ bars (Spotify)
      dots : 3 dots pulsing left→right (Other Apps)
    """
    W = 30; H = 14; FPS = 45

    def __init__(self, parent, **kw):
        kw.pop("bg", None)
        super().__init__(parent, width=self.W, height=self.H,
                         bg=PANEL, highlightthickness=0, **kw)
        self._mode   = "idle"
        self._color  = TEXT_DIM
        self._active = False
        self._phases = [i * 1.3 for i in range(4)]
        self._speeds = [0.18, 0.26, 0.21, 0.15]
        self._heights = [3] * 4
        self._dot_frame = 0
        self._draw_idle()

    def _draw_idle(self):
        self.delete("all")
        BAR_W, GAP = 3, 2
        for i in range(4):
            x1 = i*(BAR_W+GAP); x2 = x1+BAR_W
            self.create_rectangle(x1, self.H-3, x2, self.H, fill=TEXT_DIM, outline="")

    def _draw_eq(self):
        self.delete("all")
        BAR_W, GAP = 3, 2
        for i, h in enumerate(self._heights):
            x1 = i*(BAR_W+GAP); x2 = x1+BAR_W
            self.create_rectangle(x1, self.H-h, x2, self.H, fill=self._color, outline="")

    def _draw_dots(self):
        """3 dots; the active one is bright, others are dim."""
        self.delete("all")
        r = 3
        positions = [5, 15, 25]
        cy = self.H // 2
        active = (self._dot_frame // 8) % 3
        for i, cx in enumerate(positions):
            col = self._color if i == active else TEXT_DIM
            self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=col, outline="")

    def _tick_eq(self):
        if not self._active or self._mode != "eq": return
        for i in range(4):
            self._phases[i] += self._speeds[i]
            raw = math.sin(self._phases[i])*0.6 + math.sin(self._phases[i]*1.7+0.5)*0.4
            self._heights[i] = 3 + ((raw+1)/2)*11
        self._draw_eq()
        self.after(self.FPS, self._tick_eq)

    def _tick_dots(self):
        if not self._active or self._mode != "dots": return
        self._dot_frame += 1
        self._draw_dots()
        self.after(self.FPS, self._tick_dots)

    def set_mode(self, mode, color=GREEN):
        self._active = False
        self._mode   = mode
        self._color  = color
        if mode == "eq":
            self._active = True; self._tick_eq()
        elif mode == "dots":
            self._dot_frame = 0
            self._active = True; self._tick_dots()
        else:
            self._draw_idle()

    def stop(self):
        self._active = False; self._mode = "idle"
        self._color = TEXT_DIM; self._draw_idle()

class StyledEntry(tk.Frame):
    def __init__(self, parent, show="", width=30, card_bg=None, **kwargs):
        super().__init__(parent, bg=BORDER, padx=1, pady=1)
        self._e = tk.Entry(self, show=show, width=width,
                           bg=card_bg or CARD, fg=TEXT, insertbackground=GREEN,
                           relief="flat", font=FONT_MONO, highlightthickness=0, bd=4)
        self._e.pack(fill="x")
        self._e.bind("<FocusIn>",  lambda _: self.config(bg=GREEN_DIM))
        self._e.bind("<FocusOut>", lambda _: self.config(bg=BORDER))
    def get(self):          return self._e.get()
    def set(self, v):       self._e.delete(0, tk.END); self._e.insert(0, v)
    def delete(self, a, b): self._e.delete(a, b)
    def insert(self, i, v): self._e.insert(i, v)

class PlaceholderEntry(tk.Frame):
    def __init__(self, parent, placeholder="", show="", width=30, card_bg=None, **kwargs):
        super().__init__(parent, bg=BORDER, padx=1, pady=1)
        self._placeholder = placeholder
        self._show = show
        bg = card_bg or CARD
        self._e = tk.Entry(self, show="", width=width,
                           bg=bg, fg=TEXT_DIM, insertbackground=GREEN,
                           relief="flat", font=FONT_MONO, highlightthickness=0, bd=4)
        self._e.insert(0, placeholder)
        self._e.pack(fill="x")
        self._e.bind("<FocusIn>",  self._on_focus_in)
        self._e.bind("<FocusOut>", self._on_focus_out)
        self.config(bg=BORDER)
    def _on_focus_in(self, _):
        self.config(bg=GREEN_DIM)
        if self._e.get() == self._placeholder:
            self._e.delete(0, tk.END)
            self._e.config(fg=TEXT, show=self._show)
    def _on_focus_out(self, _):
        self.config(bg=BORDER)
        if not self._e.get():
            self._e.config(fg=TEXT_DIM, show="")
            self._e.insert(0, self._placeholder)
    def get(self):
        v = self._e.get()
        return "" if v == self._placeholder else v
    def set(self, v):
        self._e.config(show=self._show if v else "", fg=TEXT if v else TEXT_DIM)
        self._e.delete(0, tk.END)
        self._e.insert(0, v if v else self._placeholder)
    def delete(self, a, b): self._e.delete(a, b)
    def insert(self, i, v): self._e.insert(i, v)

class ProcessPickerDialog(tk.Toplevel):
    def __init__(self, parent, callback, main_scroll_canvas=None):
        super().__init__(parent)
        self._callback = callback
        self.title("Detect Process")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("340x322")
        self.transient(parent)
        self.grab_set()

        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            r2,g2,b2 = int(BG[1:3],16),int(BG[3:5],16),int(BG[5:7],16)
            col = ctypes.c_uint32(r2|(g2<<8)|(b2<<16))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd,35,ctypes.byref(col),ctypes.sizeof(col))
            w2 = ctypes.c_uint32(0x00FFFFFF)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd,36,ctypes.byref(w2),ctypes.sizeof(w2))
        except Exception: pass

        self._main_sc = main_scroll_canvas
        if main_scroll_canvas:
            main_scroll_canvas.unbind_all("<MouseWheel>")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        tk.Label(self, text="Running Processes", font=("Segoe UI",11,"bold"), bg=BG, fg=TEXT).pack(pady=(14,4))
        tk.Label(self, text="Double-click or press Select", font=FONT_SMALL, bg=BG, fg=TEXT_DIM).pack()

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._filter)
        sf = tk.Frame(self, bg=BORDER, padx=1, pady=1)
        sf.pack(fill="x", padx=16, pady=(10,6))
        self._search_entry = tk.Entry(sf, textvariable=self._search_var,
                                      bg=CARD, fg=TEXT_DIM, insertbackground=GREEN,
                                      relief="flat", font=FONT_MONO, highlightthickness=0, bd=4)
        self._search_entry.insert(0, "Search...")
        self._search_entry.pack(fill="x")
        sf.bind("<FocusIn>", lambda e: sf.config(bg=GREEN_DIM))
        self._search_entry.bind("<FocusIn>",  self._search_focus_in)
        self._search_entry.bind("<FocusOut>", self._search_focus_out)

        lf = tk.Frame(self, bg=BG)
        lf.pack(fill="both", expand=True, padx=16, pady=(0,10))
        sb = tk.Scrollbar(lf, bg=PURPLE_SB, troughcolor=CARD2, relief="flat", bd=0, width=10,
                          activebackground=PURPLE_LT)
        self._lb = tk.Listbox(lf, bg=CARD, fg=TEXT, selectbackground=PURPLE,
                              selectforeground=TEXT, font=FONT_MONO,
                              relief="flat", bd=0, highlightthickness=0, activestyle="none",
                              yscrollcommand=sb.set)
        sb.config(command=self._lb.yview)
        sb.pack(side="right", fill="y")
        self._lb.pack(side="left", fill="both", expand=True)
        self._lb.bind("<Double-Button-1>", self._on_select)
        self._lb.bind("<Return>", self._on_select)
        self._lb.bind("<MouseWheel>", lambda e: self._lb.yview_scroll(int(-1*(e.delta/120)),"units"))

        bf = tk.Frame(self, bg=BG)
        bf.pack(fill="x", padx=16, pady=(0,14))
        make_rounded_btn(bf, "↻ Refresh", self._load_procs,
                         CARD2, CARD, font=("Segoe UI",8), px=10, py=5, r=6,
                         text_color=TEXT_DIM, bg_parent=BG).pack(side="left")
        make_rounded_btn(bf, "Select", self._on_select,
                         GREEN, GREEN_DIM, font=("Segoe UI",9,"bold"), px=16, py=6, r=7,
                         text_color="white", bg_parent=BG).pack(side="right")

        self._all_procs = []
        self._placeholder_active = True
        self._load_procs()

    def _search_focus_in(self, _):
        self._search_entry.master.config(bg=GREEN_DIM)
        if self._placeholder_active:
            self._placeholder_active = False
            self._search_var.set("")
            self._search_entry.config(fg=TEXT)

    def _search_focus_out(self, _):
        self._search_entry.master.config(bg=BORDER)
        if not self._search_var.get():
            self._placeholder_active = True
            self._search_entry.config(fg=TEXT_DIM)
            self._search_var.set("Search...")

    def _on_close(self):
        self._restore_scroll(); self.destroy()

    def _restore_scroll(self):
        if self._main_sc:
            self._main_sc.bind_all("<MouseWheel>",
                lambda e: self._main_sc.yview_scroll(int(-1*(e.delta/120)),"units"))

    def _load_procs(self):
        self._lb.delete(0, tk.END)
        threading.Thread(
            target=lambda: self.after(0, lambda: self._populate(get_running_processes())),
            daemon=True).start()

    def _populate(self, procs):
        self._all_procs = procs; self._filter()

    def _filter(self, *_):
        if self._placeholder_active:
            q = ""
        else:
            q = self._search_var.get().lower()
        self._lb.delete(0, tk.END)
        for p in self._all_procs:
            if q in p.lower(): self._lb.insert(tk.END, p)

    def _on_select(self, _=None):
        sel = self._lb.curselection()
        if not sel: return
        self._callback(self._lb.get(sel[0]))
        self._restore_scroll(); self.destroy()


class CollapsibleSection(tk.Frame):
    def __init__(self, parent, label, bg=CARD, initially_open=True, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self._open = initially_open
        hdr = tk.Frame(self, bg=bg, cursor="hand2")
        hdr.pack(fill="x")
        self._arrow = tk.Label(hdr, text="▾" if initially_open else "▸",
                               font=("Segoe UI",8), bg=bg, fg=TEXT_DIM, cursor="hand2")
        self._arrow.pack(side="left", padx=(0,4))
        tk.Label(hdr, text=label, font=("Segoe UI",8,"bold"), bg=bg, fg=TEXT_DIM).pack(side="left")
        self._body = tk.Frame(self, bg=bg)
        if initially_open: self._body.pack(fill="x", pady=(6,0))
        hdr.bind("<Button-1>", self._toggle)
        self._arrow.bind("<Button-1>", self._toggle)

    def _toggle(self, _=None):
        self._open = not self._open
        if self._open:
            self._body.pack(fill="x", pady=(6,0)); self._arrow.config(text="▾")
        else:
            self._body.forget(); self._arrow.config(text="▸")

    @property
    def body(self): return self._body

class OtherAppRow(tk.Frame):
    def __init__(self, parent, app_data, on_delete, on_move_up, on_move_down, **kwargs):
        super().__init__(parent, bg=CARD2, **kwargs)

        top = tk.Frame(self, bg=CARD2)
        top.pack(fill="x", padx=8, pady=(5,2))
        dw = tk.Frame(top, bg=BORDER, padx=1, pady=1)
        dw.pack(side="left", fill="x", expand=True)
        self._desc_entry = tk.Entry(dw, bg=CARD2, fg=TEXT, insertbackground=GREEN,
                                    relief="flat", font=FONT_LABEL, highlightthickness=0, bd=3)
        self._desc_entry.insert(0, app_data.get("description",""))
        self._desc_entry.pack(fill="x")
        ctrl = tk.Frame(top, bg=CARD2)
        ctrl.pack(side="right", padx=(4,0))
        for sym, cmd in [("▲",on_move_up),("▼",on_move_down),("✕",on_delete)]:
            b = tk.Label(ctrl, text=sym, font=("Segoe UI",9,"bold"),
                         bg=CARD2, fg=TEXT_DIM, cursor="hand2", padx=3)
            b.pack(side="left")
            b.bind("<Enter>",    lambda e,w=b: w.config(fg=TEXT))
            b.bind("<Leave>",    lambda e,w=b: w.config(fg=TEXT_DIM))
            b.bind("<Button-1>", lambda e,c=cmd: c())

        pr = tk.Frame(self, bg=CARD2)
        pr.pack(fill="x", padx=8, pady=(0,3))
        tk.Label(pr, text="Process", font=FONT_SMALL, bg=CARD2, fg=TEXT_DIM, width=9, anchor="w").pack(side="left")
        pw = tk.Frame(pr, bg=BORDER, padx=1, pady=1)
        pw.pack(side="left", fill="x", expand=True)
        self._proc_entry = tk.Entry(pw, bg=CARD2, fg=TEXT, insertbackground=GREEN,
                                    relief="flat", font=FONT_MONO, highlightthickness=0, bd=3)
        self._proc_entry.insert(0, app_data.get("process",""))
        self._proc_entry.pack(fill="x")
        make_rounded_btn(pr, "Detect", self._detect,
                         PURPLE, PURPLE_LT, font=("Segoe UI",8), px=7, py=3, r=5,
                         text_color=TEXT, bg_parent=CARD2).pack(side="left", padx=(5,0))

        sr = tk.Frame(self, bg=CARD2)
        sr.pack(fill="x", padx=8, pady=(0,3))
        tk.Label(sr, text="Status text", font=FONT_SMALL, bg=CARD2, fg=TEXT_DIM, width=9, anchor="w").pack(side="left")
        sw = tk.Frame(sr, bg=BORDER, padx=1, pady=1)
        sw.pack(side="left", fill="x", expand=True)
        self._status_entry = tk.Entry(sw, bg=CARD2, fg=TEXT, insertbackground=GREEN,
                                      relief="flat", font=FONT_MONO, highlightthickness=0, bd=3)
        self._status_entry.insert(0, app_data.get("status_text",""))
        self._status_entry.pack(fill="x")
        ew = tk.Frame(sr, bg=BORDER, padx=1, pady=1)
        ew.pack(side="left", padx=(5,0))
        self._emoji_entry = tk.Entry(ew, width=12, bg=CARD2, fg=TEXT, insertbackground=GREEN,
                                     relief="flat", font=FONT_MONO, highlightthickness=0, bd=3)
        self._emoji_entry.insert(0, app_data.get("emoji",":app:"))
        self._emoji_entry.pack()

        self._enabled_var = tk.BooleanVar(value=app_data.get("enabled", True))
        er = tk.Frame(self, bg=CARD2)
        er.pack(fill="x", padx=8, pady=(0,4))
        tk.Checkbutton(er, text="Enabled", variable=self._enabled_var,
                       bg=CARD2, fg=TEXT_DIM, activebackground=CARD2,
                       selectcolor=CARD, font=FONT_SMALL, highlightthickness=0, bd=0).pack(side="left")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

    def _detect(self):
        top = self.winfo_toplevel()
        ProcessPickerDialog(top, self._set_proc,
                            main_scroll_canvas=getattr(top, "_main_scroll_canvas", None))

    def _set_proc(self, name):
        self._proc_entry.delete(0, tk.END); self._proc_entry.insert(0, name)

    def get_data(self):
        return {
            "process":     self._proc_entry.get().strip(),
            "status_text": self._status_entry.get().strip(),
            "emoji":       self._emoji_entry.get().strip(),
            "description": self._desc_entry.get().strip(),
            "enabled":     self._enabled_var.get(),
        }


def build_card_section(parent, title, builder_fn):
    PADX = 16; RADIUS = 10; PAD_I = 12

    section = tk.Frame(parent, bg=BG)
    section.pack(fill="x", padx=PADX, pady=(0,12))
    tk.Label(section, text=title, font=("Segoe UI",8,"bold"),
             bg=BG, fg=TEXT_DIM).pack(anchor="w", pady=(0,5))

    cvs = tk.Canvas(section, bg=BG, highlightthickness=0, bd=0)
    cvs.pack(fill="x")
    inner = tk.Frame(cvs, bg=CARD)
    builder_fn(inner)

    def _redraw(cw, ch):
        draw_rounded_card(cvs, cw, ch, fill=CARD, outline=BORDER, r=RADIUS)
        cvs.delete("iwin")
        cvs.create_window(cw//2, ch//2, window=inner, width=cw-2*PAD_I, anchor="center", tags="iwin")

    def _place(event=None):
        inner.update_idletasks()
        ih = inner.winfo_reqheight()
        th = ih + 2*PAD_I
        cw = cvs.winfo_width() if cvs.winfo_width() > 1 else section.winfo_reqwidth()
        cvs.config(height=th)
        _redraw(cw, th)

    def _on_cfg(event):
        inner.update_idletasks()
        ih = inner.winfo_reqheight()
        th = ih + 2*PAD_I
        cvs.config(height=th)
        _redraw(event.width, th)

    cvs.bind("<Configure>", _on_cfg)
    section.after(10, _place)
    inner._refresh = _place
    return inner

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title("My Activity on Slack")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("520x630") 
        self._set_icon()
        self._apply_dark_titlebar()
        self._other_app_rows = []
        self._build_ui()
        self._load_saved_config()
        self._update_status("idle", "Disconnected", TEXT_DIM)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_icon(self):
        try:
            p = resource_path("icon.ico")
            if os.path.exists(p): self.iconbitmap(p)
        except Exception: pass

    def _apply_dark_titlebar(self):
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            r,g,b = int(BG[1:3],16),int(BG[3:5],16),int(BG[5:7],16)
            col = ctypes.c_uint32(r|(g<<8)|(b<<16))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd,35,ctypes.byref(col),ctypes.sizeof(col))
            w2 = ctypes.c_uint32(0x00FFFFFF)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd,36,ctypes.byref(w2),ctypes.sizeof(w2))
            d = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd,20,ctypes.byref(d),ctypes.sizeof(d))
        except Exception: pass

    def _build_ui(self):
        hdr = tk.Frame(self, bg=PANEL, height=52)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tf = tk.Frame(hdr, bg=PANEL)
        tf.pack(side="left", pady=6)
        tk.Label(tf, text=" My Activity Status",
                 font=("Helvetica",25,"bold"), bg=PANEL, fg=TEXT).pack(anchor="w")
        
        srow = tk.Frame(self, bg=PANEL, height=28)
        srow.pack(fill="x"); srow.pack_propagate(False)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        inner_s = tk.Frame(srow, bg=PANEL)
        inner_s.pack(side="left", padx=18, fill="y")
        self._indicator = StatusIndicator(inner_s)
        self._indicator.pack(side="left", pady=7)
        self._status_lbl = tk.Label(inner_s, text="", font=FONT_SMALL, bg=PANEL, fg=TEXT_DIM)
        self._status_lbl.pack(side="left", padx=(8,0))

        sc = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(self, orient="vertical", command=sc.yview,
                          bg=PURPLE_SB, troughcolor=CARD2, relief="flat", bd=0, width=12,
                          activebackground=PURPLE_LT)
        sc.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        sc.pack(side="left", fill="both", expand=True)
        self._main_scroll_canvas = sc

        sf = tk.Frame(sc, bg=BG)
        win_id = sc.create_window((0,0), window=sf, anchor="nw")
        sf.bind("<Configure>", lambda _: sc.configure(scrollregion=sc.bbox("all")))
        sc.bind("<Configure>",  lambda e: sc.itemconfig(win_id, width=e.width))
        sc.bind_all("<MouseWheel>", lambda e: sc.yview_scroll(int(-1*(e.delta/120)),"units"))
        self._scroll_frame = sf

        build_card_section(sf, "Slack Token",      self._build_slack_fields)
        build_card_section(sf, "Spotify Playback", self._build_spotify_playback_fields)
        build_card_section(sf, "Other Apps",       self._build_other_apps_fields)
        np_outer = tk.Frame(sf, bg=BG)
        np_outer.pack(fill="x", padx=16, pady=(0,12))
        npc = tk.Canvas(np_outer, bg=BG, highlightthickness=0, bd=0, height=78)
        npc.pack(fill="x")
        npi = tk.Frame(npc, bg=CARD)
        tk.Label(npi, text="NOW PLAYING", font=("Segoe UI",7,"bold"),
                 bg=CARD, fg=TEXT_DIM).pack(anchor="w")
        self._np_lbl = tk.Label(npi, text="Nothing Happens... :3", font=FONT_BIG,
                                bg=CARD, fg=GREEN, wraplength=420, justify="left")
        self._np_lbl.pack(anchor="w", pady=(2,0))
        self._np_time_lbl = tk.Label(npi, text="", font=FONT_SMALL,
                                     bg=CARD, fg=TEXT_DIM)
        self._np_time_lbl.pack(anchor="w")

        def _draw_np(event=None):
            w = npc.winfo_width() if npc.winfo_width() > 1 else 488
            h = int(npc["height"])
            draw_rounded_card(npc, w, h)
            npc.create_window(w//2, h//2, window=npi, width=w-28, anchor="center")

        npc.bind("<Configure>", lambda e: _draw_np(e))
        np_outer.after(10, _draw_np)

        log_outer = tk.Frame(sf, bg=BG)
        log_outer.pack(fill="both", expand=True, padx=16, pady=(0,12))
        tk.Label(log_outer, text="LOG", font=("Segoe UI",7,"bold"),
                 bg=BG, fg=TEXT_DIM).pack(anchor="w", pady=(0,4))
        self._log = tk.Text(log_outer, height=5, bg=PANEL, fg=TEXT_DIM, font=FONT_MONO,
                            relief="flat", bd=0, highlightthickness=1,
                            highlightbackground=BORDER, state="disabled", wrap="word")
        self._log.pack(fill="both", expand=True)

        bf = tk.Frame(sf, bg=BG)
        bf.pack(fill="x", padx=16, pady=(0,16))
        self._btn_auth  = self._make_btn(bf, "Spotify Authorization", self._do_auth,  PURPLE, PURPLE_LT)
        self._btn_auth.pack(side="left", padx=(3,8))
        self._btn_start = self._make_btn(bf, "Start", self._do_start, GREEN, GREEN_DIM)
        self._btn_start.pack(side="left", padx=(0,8))
        self._btn_stop  = self._make_btn(bf, "Stop",  self._do_stop,  RED,   "#a03434", state="disabled")
        self._btn_stop.pack(side="left")

    def _build_slack_fields(self, parent):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x")
        tk.Label(row, text="xoxp- token", font=FONT_LABEL, bg=CARD, fg=TEXT_DIM, width=14, anchor="w").pack(side="left")
        self._slack_tok = StyledEntry(row, show="•", width=36)
        self._slack_tok.pack(side="left", fill="x", expand=True)

    def _build_spotify_playback_fields(self, parent):
        cred = CollapsibleSection(parent, "API Credentials", bg=CARD, initially_open=True)
        cred.pack(fill="x", pady=(4,0))

        r1 = tk.Frame(cred.body, bg=CARD)
        r1.pack(fill="x", pady=(0,8))
        tk.Label(r1, text="Client ID", font=FONT_LABEL, bg=CARD, fg=TEXT_DIM, width=14, anchor="w").pack(side="left")
        self._sp_id = StyledEntry(r1, width=36)
        self._sp_id.pack(side="left", fill="x", expand=True)

        r2 = tk.Frame(cred.body, bg=CARD)
        r2.pack(fill="x", pady=(0,4))
        tk.Label(r2, text="Client Secret", font=FONT_LABEL, bg=CARD, fg=TEXT_DIM, width=14, anchor="w").pack(side="left")
        self._sp_secret = StyledEntry(r2, show="•", width=36)
        self._sp_secret.pack(side="left", fill="x", expand=True)

        tk.Label(cred.body,
                 text="ℹ: You need Spotify Premium to synk your status",
                 font=FONT_MONO, bg=CARD, fg=TEXT_DIM, wraplength=380, justify="left"
                 ).pack(anchor="w", pady=(6,4))

        play = CollapsibleSection(parent, "Playback Settings", bg=CARD, initially_open=True)
        play.pack(fill="x", pady=(8,4))

        r3 = tk.Frame(play.body, bg=CARD)
        r3.pack(fill="x", pady=(0,8))
        tk.Label(r3, text="Emoji status", font=FONT_LABEL, bg=CARD, fg=TEXT_DIM, width=14, anchor="w").pack(side="left")
        self._emoji = StyledEntry(r3, width=14)
        self._emoji.set(":spotify_logo:")
        self._emoji.pack(side="left")

        r4 = tk.Frame(play.body, bg=CARD)
        r4.pack(fill="x", pady=(0,4))
        tk.Label(r4, text="Interval (sec)", font=FONT_LABEL, bg=CARD, fg=TEXT_DIM, width=14, anchor="w").pack(side="left")
        self._interval = StyledEntry(r4, width=6)
        self._interval.set("1")
        self._interval.pack(side="left")

    def _build_other_apps_fields(self, parent):
        self._other_apps_parent = parent

        hdr = tk.Frame(parent, bg=CARD)
        hdr.pack(fill="x", pady=(4,6))
        tk.Label(hdr, text="App Priority", font=("Segoe UI",8,"bold"), bg=CARD, fg=TEXT_DIM).pack(side="left")
        make_rounded_btn(hdr, "Detect Process",
                         lambda: ProcessPickerDialog(
                             self, lambda n: messagebox.showinfo("Process Detected", f"Running:\n\n{n}\n\nPaste into any Process field."),
                             main_scroll_canvas=self._main_scroll_canvas),
                         PURPLE, PURPLE_LT, font=("Segoe UI",8), px=8, py=4, r=6,
                         text_color=TEXT, bg_parent=CARD).pack(side="right")

        sw = tk.Frame(parent, bg=CARD)
        sw.pack(fill="x")

        oa_sb = tk.Scrollbar(sw, orient="vertical",
                              bg=PURPLE_SB, troughcolor=CARD2,
                              relief="flat", bd=0, width=14,
                              activebackground=PURPLE_LT)
        self._oa_canvas = tk.Canvas(sw, bg=CARD, highlightthickness=0, bd=0, height=280)
        self._oa_canvas.configure(yscrollcommand=oa_sb.set)
        oa_sb.config(command=self._oa_canvas.yview)
        oa_sb.pack(side="right", fill="y")
        self._oa_canvas.pack(side="left", fill="both", expand=True)

        self._other_apps_container = tk.Frame(self._oa_canvas, bg=CARD)
        oa_win = self._oa_canvas.create_window((0,0), window=self._other_apps_container, anchor="nw")

        def _oa_cfg(_):
            self._oa_canvas.configure(scrollregion=self._oa_canvas.bbox("all"))
            self._oa_canvas.itemconfig(oa_win, width=self._oa_canvas.winfo_width())

        self._other_apps_container.bind("<Configure>", _oa_cfg)
        self._oa_canvas.bind("<Configure>", lambda e: self._oa_canvas.itemconfig(oa_win, width=e.width))

        def _oa_enter(_): self._oa_canvas.bind_all("<MouseWheel>", _oa_scroll)
        def _oa_leave(_): self._oa_canvas.bind_all("<MouseWheel>",
                              lambda e: self._main_scroll_canvas.yview_scroll(int(-1*(e.delta/120)),"units"))
        def _oa_scroll(e): self._oa_canvas.yview_scroll(int(-1*(e.delta/120)),"units")

        self._oa_canvas.bind("<Enter>", _oa_enter)
        self._oa_canvas.bind("<Leave>", _oa_leave)
        self._other_apps_container.bind("<Enter>", _oa_enter)
        self._other_apps_container.bind("<Leave>", _oa_leave)

        ar = tk.Frame(parent, bg=CARD)
        ar.pack(fill="x", pady=(6,4))
        make_rounded_btn(ar, "＋ Add App", self._add_other_app,
                         CARD2, BORDER, font=("Segoe UI", 8), px=10, py=5, r=6,
                         text_color=TEXT_DIM, bg_parent=CARD).pack(side="left")
        self._count_lbl = tk.Label(ar, text="0 / 5", font=FONT_SMALL, bg=CARD, fg=TEXT_DIM)
        self._count_lbl.pack(side="right", padx=4)

    def _add_other_app(self, app_data=None):
        if len(self._other_app_rows) >= 5:
            messagebox.showinfo("Limit reached", "Maximum 5 app rules allowed."); return
        if app_data is None:
            app_data = {"process":"","status_text":"","emoji":":app:","description":"New App","enabled":True}
        row = OtherAppRow(
            self._other_apps_container, app_data,
            on_delete    = lambda: self._remove_other_app(row),
            on_move_up   = lambda: self._move_other_app(row, -1),
            on_move_down = lambda: self._move_other_app(row, +1),
        )
        row.pack(fill="x", pady=(0,2))

        def _bind_mw(widget):
            widget.bind("<Enter>", lambda e: self._oa_canvas.bind_all("<MouseWheel>",
                lambda ev: self._oa_canvas.yview_scroll(int(-1*(ev.delta/120)),"units")))
            widget.bind("<Leave>", lambda e: self._oa_canvas.bind_all("<MouseWheel>",
                lambda ev: self._main_scroll_canvas.yview_scroll(int(-1*(ev.delta/120)),"units")))
            for child in widget.winfo_children():
                _bind_mw(child)
        _bind_mw(row)

        self._other_app_rows.append(row)
        self._update_count_label()

    def _remove_other_app(self, row):
        if row in self._other_app_rows: self._other_app_rows.remove(row)
        row.destroy(); self._update_count_label()

    def _move_other_app(self, row, direction):
        idx = self._other_app_rows.index(row)
        new = idx + direction
        if new < 0 or new >= len(self._other_app_rows): return
        self._other_app_rows[idx], self._other_app_rows[new] = \
            self._other_app_rows[new], self._other_app_rows[idx]
        for r in self._other_app_rows: r.pack_forget()
        for r in self._other_app_rows: r.pack(fill="x", pady=(0,2))

    def _update_count_label(self):
        n = len(self._other_app_rows)
        if hasattr(self, "_count_lbl"):
            self._count_lbl.config(text=f"{n} / 5", fg=AMBER if n >= 5 else TEXT_DIM)

    def _load_saved_config(self):
        cfg = load_config()
        if cfg.get("sp_id"):     self._sp_id.set(cfg["sp_id"])
        if cfg.get("sp_secret"): self._sp_secret.set(cfg["sp_secret"])
        if cfg.get("slack_tok"): self._slack_tok.set(cfg["slack_tok"])
        if cfg.get("emoji"):     self._emoji.set(cfg["emoji"])
        if cfg.get("interval"):  self._interval.set(cfg["interval"])
        apps = cfg.get("other_apps") or DEFAULT_OTHER_APPS
        for a in apps: self._add_other_app(app_data=a)

    def _save_config(self):
        save_config({
            "sp_id":      self._sp_id.get().strip(),
            "sp_secret":  self._sp_secret.get().strip(),
            "slack_tok":  self._slack_tok.get().strip(),
            "emoji":      self._emoji.get().strip(),
            "interval":   self._interval.get().strip(),
            "other_apps": [r.get_data() for r in self._other_app_rows],
        })

    def _on_close(self):
        self._save_config(); self.destroy()

    def _make_btn(self, parent, text, cmd, color, hover_color, state="normal"):
        import tkinter.font as tkfont
        R=8; PX=14; PY=8; F=("Segoe UI",9,"bold")
        f = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        bw = f.measure(text)+PX*2; bh = f.metrics("linespace")+PY*2
        cvs = tk.Canvas(parent, width=bw, height=bh,
                        highlightthickness=0, bd=0, bg=BG, cursor="hand2")
        cvs._enabled = (state!="disabled")
        cvs._color   = color if cvs._enabled else BORDER
        cvs._hov     = hover_color
        cvs._tcol    = "white" if cvs._enabled else TEXT_DIM
        cvs._lbl     = text

        def _rd(c=None):
            cvs.delete("all"); bc=c or cvs._color
            cw,ch = int(cvs["width"]),int(cvs["height"])
            for x1,y1,x2,y2,st in [(0,0,2*R,2*R,90),(cw-2*R,0,cw,2*R,0),
                                     (0,ch-2*R,2*R,ch,180),(cw-2*R,ch-2*R,cw,ch,270)]:
                cvs.create_arc(x1,y1,x2,y2,start=st,extent=90,fill=bc,outline="")
            cvs.create_rectangle(R,0,cw-R,ch,fill=bc,outline="")
            cvs.create_rectangle(0,R,cw,ch-R,fill=bc,outline="")
            cvs.create_text(cw//2,ch//2,text=cvs._lbl,font=F,fill=cvs._tcol)

        cvs._redraw=_rd; _rd()
        cvs.bind("<Enter>",    lambda _: _rd(cvs._hov)   if cvs._enabled else None)
        cvs.bind("<Leave>",    lambda _: _rd(cvs._color) if cvs._enabled else None)
        cvs.bind("<Button-1>", lambda _: cmd()           if cvs._enabled else None)
        return cvs

    def _enable_btn(self, btn, color, hover):
        btn._enabled=True; btn._color=color; btn._hov=hover
        btn._tcol="white"; btn.config(cursor="hand2"); btn._redraw()

    def _disable_btn(self, btn):
        btn._enabled=False; btn._color=BORDER
        btn._tcol=TEXT_DIM; btn.config(cursor="arrow"); btn._redraw()

    def _update_status(self, mode, text, color):
        self._status_lbl.config(text=text, fg=color)
        self._indicator.set_mode(mode, color)

    def _log_msg(self, text):
        self._log.config(state="normal")
        self._log.insert("end", f"[{datetime.datetime.now():%H:%M:%S}] {text}\n")
        self._log.see("end"); self._log.config(state="disabled")

    def _set_now_playing(self, text, time_str=""):
        self._np_lbl.config(text=text or "-", fg=GREEN if text else TEXT_DIM)
        self._np_time_lbl.config(text=time_str)

    def _do_auth(self):
        global auth_code
        cid=self._sp_id.get().strip(); sec=self._sp_secret.get().strip()
        if not cid or not sec:
            messagebox.showerror("Error!", "Fill in Spotify Client ID and Client Secret first."); return
        auth_code=None
        self._update_status("dots","Waiting for Spotify auth...", AMBER)
        self._log_msg("Opening browser for Spotify authorisation...")

        def _thread():
            global auth_code, access_token, refresh_token
            try:
                get_auth_code(cid)
                if not auth_code:
                    self.after(0, lambda: self._update_status("idle","Authorization failed",RED))
                    self.after(0, lambda: self._log_msg("Authorization code not received")); return
                tokens = get_tokens(auth_code, cid, sec)
                access_token  = tokens.get("access_token")
                refresh_token = tokens.get("refresh_token")
                if not access_token:
                    self.after(0, lambda: self._update_status("idle","Invalid Token",RED))
                    self.after(0, lambda: self._log_msg(f"Token Error: {tokens}")); return
                self.after(0, lambda: self._update_status("idle","Authorized",GREEN))
                self.after(0, lambda: self._log_msg("Spotify authorized!"))
            except Exception as e:
                self.after(0, lambda: self._log_msg(f"Auth Error: {e}"))
                self.after(0, lambda: self._update_status("idle","Error",RED))

        threading.Thread(target=_thread, daemon=True).start()

    def _do_start(self):
        global running, worker_thread
        if running: return
        running=True
        self._disable_btn(self._btn_start)
        self._enable_btn(self._btn_stop, RED, "#a03434")
        mode="Spotify + Other Apps" if access_token else "Other Apps only"
        self._update_status("dots", f"Running  {mode}", GREEN)
        self._log_msg(f"Started ({mode})")
        worker_thread=threading.Thread(target=self._worker, daemon=True)
        worker_thread.start()

    def _do_stop(self):
        global running
        running=False
        slack_tok=self._slack_tok.get().strip()
        if slack_tok:
            try: set_slack_status("","",slack_tok)
            except Exception: pass
        self._disable_btn(self._btn_stop)
        self._enable_btn(self._btn_start, GREEN, GREEN_DIM)
        self._update_status("idle","Stopped",TEXT_DIM)
        self._set_now_playing(None)
        self._log_msg("Stopped. Slack status cleared.")
        _app_timers.clear()

    def _worker(self):
        global running, access_token
        cid=self._sp_id.get().strip(); sec=self._sp_secret.get().strip()
        slack=self._slack_tok.get().strip()
        emoji=self._emoji.get().strip() or ":spotify_logo:"
        try: interval=float(self._interval.get().strip())
        except ValueError: interval=1.0

        last_track=None; last_app=None
        refresh_count=0; refresh_every=int(3000/max(interval,0.5))
        cur_mode="dots"

        while running:
            try:
                if access_token and refresh_count>=refresh_every:
                    new=refresh_access_token_fn(refresh_token,cid,sec)
                    if new: access_token=new; self.after(0,lambda: self._log_msg("Spotify token renewed"))
                    refresh_count=0

                current=get_current_track(access_token) if access_token else None
                current_name=current.rsplit(" : ",1)[0] if current else None

                if current:
                    if cur_mode!="eq":
                        self.after(0,lambda: self._update_status("eq","Running - Spotify Playback",GREEN))
                        cur_mode="eq"
                    if current_name!=last_track:
                        self.after(0,lambda c=current: self._set_now_playing(c))
                        self.after(0,lambda c=current: self._log_msg(f"Playback: {c}"))
                        set_slack_status(current,emoji,slack)
                        last_track=current_name; last_app=None
                    else:
                        set_slack_status(current,emoji,slack)
                        self.after(0,lambda c=current: self._set_now_playing(c))
                else:
                    if cur_mode!="dots":
                        self.after(0,lambda: self._update_status("dots","Running - Other Apps",GREEN))
                        cur_mode="dots"

                    matched=None
                    try:
                        procs={p.info["name"].lower() for p in psutil.process_iter(["name"]) if p.info["name"]}
                    except Exception: procs=set()

                    for row in self._other_app_rows:
                        d=row.get_data()
                        if d["enabled"] and d["process"].lower() in procs:
                            matched=d; break

                    if matched:
                        key=matched["process"]
                        now=time.time()
                        if key!=last_app:
                            _app_timers[key]=now
                            self.after(0,lambda d=matched["description"]: self._log_msg(f"App detected: {d}"))
                            last_app=key; last_track=None

                        elapsed=now - _app_timers.get(key, now)
                        time_str=fmt_duration(elapsed)
                        slack_text=f"{matched['status_text']} : {time_str}"
                        set_slack_status(slack_text, matched["emoji"], slack)

                        desc=matched["description"]
                        tstr=f"Time on this app: {time_str}"
                        self.after(0,lambda d=desc,t=tstr: self._set_now_playing(d,t))
                    else:
                        if last_track is not None or last_app is not None:
                            self.after(0,lambda: self._set_now_playing(None))
                            self.after(0,lambda: self._log_msg("Nothing active - status cleared."))
                            set_slack_status("","",slack)
                            last_track=None; last_app=None

                refresh_count+=1
                time.sleep(interval)

            except Exception as e:
                self.after(0,lambda err=e: self._log_msg(f"Err: {err}"))
                time.sleep(5)


if __name__ == "__main__":
    app = App()
    app.deiconify()
    app.mainloop()