import time
import requests
import json
import webbrowser
import threading
import tkinter as tk
import sys
import os
from tkinter import ttk, messagebox
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from pathlib import Path


def get_base_dir():
    if getattr(sys, 'frozen', False): 
        return Path(sys.executable).parent
    return Path(__file__).parent

CONFIG_FILE = get_base_dir() / "spotify_slack_config.json"
def resource_path(relative_path):
    """Găsește calea resursei, funcționează atât în .py cât și în .exe"""
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
BG         = "#0f0f13"
PANEL      = "#17171f"
CARD       = "#1e1e2a"
BORDER     = "#2a2a3a"
GREEN      = "#1db954"   
GREEN_DIM  = "#158a3e"
PURPLE     = "#4a3fa0"
PURPLE_LT  = "#7c6fcd"
TEXT       = "#e8e8f0"
TEXT_DIM   = "#6e6e88"
RED        = "#e05252"
AMBER      = "#e0a832"

FONT_TITLE  = ("Segoe UI", 13, "bold")
FONT_LABEL  = ("Segoe UI", 9)
FONT_SMALL  = ("Segoe UI", 8)
FONT_MONO   = ("Consolas", 9)
FONT_BIG    = ("Segoe UI", 11, "bold")
FONT_GIANT  = ("Segoe UI", 16, "bold")

auth_code     = None
access_token  = None
refresh_token = None
running       = False
worker_thread = None


SPOTIFY_REDIRECT_URI = "http://127.0.0.1:9090/callback"
SPOTIFY_SCOPE        = "user-read-currently-playing user-read-playback-state"


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            auth_code = params["code"][0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorized! You may close this window.")

    def log_message(self, *_):
        pass


def get_auth_code(client_id):
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SPOTIFY_SCOPE,
    }
    url = "https://accounts.spotify.com/authorize?" + urlencode(params)
    webbrowser.open(url)
    server = HTTPServer(("127.0.0.1", 9090), CallbackHandler)
    server.handle_request()


def get_tokens(code, client_id, client_secret):
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
        },
        auth=(client_id, client_secret),
    )
    return resp.json()


def refresh_access_token_fn(ref_tok, client_id, client_secret):
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "refresh_token", "refresh_token": ref_tok},
        auth=(client_id, client_secret),
    )
    return resp.json().get("access_token")


def format_ms(ms):
    total_sec = ms // 1000
    return f"{total_sec // 60}:{total_sec % 60:02d}"


def get_current_track(tok):
    resp = requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers={"Authorization": f"Bearer {tok}"},
    )
    if resp.status_code == 200 and resp.content:
        data = resp.json()
        if data.get("is_playing") and data.get("item"):
            track   = data["item"]["name"]
            artist  = data["item"]["artists"][0]["name"]
            elapsed = format_ms(data.get("progress_ms", 0))
            dur     = format_ms(data["item"]["duration_ms"])
            return f"{artist} - {track} : {elapsed}/{dur}"
    return None


def set_slack_status(text, emoji, slack_token):
    profile = {
        "status_text":       text if text else "",
        "status_emoji":      emoji if text else "",
        "status_expiration": 0,
    }
    requests.post(
        "https://slack.com/api/users.profile.set",
        headers={
            "Authorization": f"Bearer {slack_token}",
            "Content-Type":  "application/json",
        },
        data=json.dumps({"profile": profile}),
    )


def rounded_rect(canvas, x1, y1, x2, y2, r=12, **kwargs):
    canvas.create_arc(x1,     y1,     x1+2*r, y1+2*r, start=90,  extent=90,  style="pieslice", **kwargs)
    canvas.create_arc(x2-2*r, y1,     x2,     y1+2*r, start=0,   extent=90,  style="pieslice", **kwargs)
    canvas.create_arc(x1,     y2-2*r, x1+2*r, y2,     start=180, extent=90,  style="pieslice", **kwargs)
    canvas.create_arc(x2-2*r, y2-2*r, x2,     y2,     start=270, extent=90,  style="pieslice", **kwargs)
    canvas.create_rectangle(x1+r, y1,   x2-r, y2,   **kwargs)
    canvas.create_rectangle(x1,   y1+r, x2,   y2-r, **kwargs)


class StyledEntry(tk.Frame):
    """Entry with nice dark border styling."""
    def __init__(self, parent, show="", width=30, **kwargs):
        super().__init__(parent, bg=BORDER, padx=1, pady=1)
        self._entry = tk.Entry(
            self, show=show, width=width,
            bg=CARD, fg=TEXT, insertbackground=GREEN,
            relief="flat", font=FONT_MONO,
            highlightthickness=0, bd=4,
        )
        self._entry.pack(fill="x")
        self._entry.bind("<FocusIn>",  lambda _: self.config(bg=GREEN_DIM))
        self._entry.bind("<FocusOut>", lambda _: self.config(bg=BORDER))

    def get(self):  return self._entry.get()
    def set(self, v):
        self._entry.delete(0, tk.END)
        self._entry.insert(0, v)
    def delete(self, a, b): self._entry.delete(a, b)
    def insert(self, i, v): self._entry.insert(i, v)


class EqBars(tk.Canvas):
    NUM_BARS   = 4
    BAR_W      = 3
    BAR_GAP    = 2
    MAX_H      = 14
    MIN_H      = 3
    FPS        = 40

    def __init__(self, parent, **kwargs):
        w = self.NUM_BARS * self.BAR_W + (self.NUM_BARS - 1) * self.BAR_GAP
        kwargs.pop("bg", None)
        super().__init__(parent, width=w, height=self.MAX_H,
                         bg=PANEL, highlightthickness=0, **kwargs)
        self._active = False
        self._color  = TEXT_DIM
        import math
        self._phases  = [i * 1.3 for i in range(self.NUM_BARS)]
        self._speeds  = [0.18, 0.26, 0.21, 0.15]
        self._heights = [self.MIN_H] * self.NUM_BARS
        self._draw()

    def _draw(self):
        self.delete("all")
        for i, h in enumerate(self._heights):
            x1 = i * (self.BAR_W + self.BAR_GAP)
            x2 = x1 + self.BAR_W
            y2 = self.MAX_H
            y1 = y2 - h
            r = 1
            self.create_rectangle(x1, y1 + r, x2, y2, fill=self._color, outline="")
            self.create_rectangle(x1, y1, x2, y1 + r, fill=self._color, outline="")

    def _animate(self):
        if not self._active:
            return
        import math
        for i in range(self.NUM_BARS):
            self._phases[i] += self._speeds[i]
            raw = (math.sin(self._phases[i]) * 0.6 +
                   math.sin(self._phases[i] * 1.7 + 0.5) * 0.4)
            norm = (raw + 1) / 2
            self._heights[i] = self.MIN_H + norm * (self.MAX_H - self.MIN_H)
        self._draw()
        self.after(self.FPS, self._animate)

    def set_color(self, color, pulse=False):
        self._color  = color
        self._active = pulse
        if pulse:
            self._animate()
        else:
            self._heights = [self.MIN_H] * self.NUM_BARS
            self._draw()

    def stop(self):
        self._active = False
        self._color  = TEXT_DIM
        self._heights = [self.MIN_H] * self.NUM_BARS
        self._draw()

AnimatedDot = EqBars


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title("Spotify status on Slack")
        self.iconbitmap(os.path.join(os.path.dirname(__file__), "icon.ico"))
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("500x680")

        # ── Iconița ferestrei ─────────────────────────────────────────────────
        self._set_icon()

        self._apply_dark_titlebar()
        self._build_ui()
        self._load_saved_config()
        self._update_status("Disconected", TEXT_DIM)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_icon(self):
        """Setează iconița ferestrei — funcționează și în .exe"""
        icon_path = resource_path("icon.ico")
        try:
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    def _apply_dark_titlebar(self):
        """Use Windows DWM API to paint the caption bar with BG color."""
        try:
            import ctypes
            import ctypes.wintypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if hwnd == 0:
                hwnd = self.winfo_id()

            r, g, b = int(BG[1:3], 16), int(BG[3:5], 16), int(BG[5:7], 16)
            colorref = ctypes.c_uint32(r | (g << 8) | (b << 16))

            DWMWA_CAPTION_COLOR = 35
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_CAPTION_COLOR,
                ctypes.byref(colorref),
                ctypes.sizeof(colorref),
            )

            white = ctypes.c_uint32(0x00FFFFFF)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 36,
                ctypes.byref(white),
                ctypes.sizeof(white),
            )

            dark = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20,
                ctypes.byref(dark),
                ctypes.sizeof(dark),
            )
        except Exception:
            pass 

    def _build_ui(self):
        hdr = tk.Frame(self, bg=PANEL, height=52) 
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        title_frame = tk.Frame(hdr, bg=PANEL)
        title_frame.pack(side="left", pady=6)       
        FONT_GIANT = ("Helvetica", 25, "bold")
        tk.Label(title_frame, text=" Spotify status on Slack", font=FONT_GIANT, bg=PANEL, fg=TEXT).pack(anchor="w")

        status_row = tk.Frame(self, bg=PANEL, height=28)  
        status_row.pack(fill="x")
        status_row.pack_propagate(False)

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x")

        inner_s = tk.Frame(status_row, bg=PANEL)
        inner_s.pack(side="left", padx=18, fill="y")

        self._dot = EqBars(inner_s)
        self._dot.pack(side="left", pady=7)

        self._status_lbl = tk.Label(inner_s, text="", font=FONT_SMALL, bg=PANEL, fg=TEXT_DIM)
        self._status_lbl.pack(side="left", padx=(8, 0))

        scroll_frame = tk.Frame(self, bg=BG)
        scroll_frame.pack(fill="both", expand=True, padx=16, pady=12)

        self._build_section(scroll_frame, "Spotify Credentials", self._build_spotify_fields)
        self._build_section(scroll_frame, "Slack Token",         self._build_slack_fields)
        self._build_section(scroll_frame, "Configurations",      self._build_settings_fields)

        np_outer = tk.Frame(self, bg=BG)
        np_outer.pack(fill="x", padx=16, pady=(0, 12))

        np_cvs = tk.Canvas(np_outer, bg=BG, highlightthickness=0, bd=0, height=68)
        np_cvs.pack(fill="x")

        np_inner = tk.Frame(np_cvs, bg=CARD)
        tk.Label(np_inner, text="NOW PLAYING", font=("Segoe UI", 7, "bold"),
                 bg=CARD, fg=TEXT_DIM).pack(anchor="w")
        self._np_lbl = tk.Label(np_inner, text="Nothing Happens... :3", font=FONT_BIG,
                                bg=CARD, fg=GREEN, wraplength=420, justify="left")
        self._np_lbl.pack(anchor="w", pady=(2, 0))

        def _draw_np(event=None):
            np_cvs.delete("all")
            w = np_cvs.winfo_width() if np_cvs.winfo_width() > 1 else 468
            h = int(np_cvs["height"])
            r = 10
            for kw in [{"fill": CARD, "outline": ""}]:
                np_cvs.create_arc(0,     0,     2*r,   2*r,   start=90,  extent=90,  style="pieslice", **kw)
                np_cvs.create_arc(w-2*r, 0,     w,     2*r,   start=0,   extent=90,  style="pieslice", **kw)
                np_cvs.create_arc(0,     h-2*r, 2*r,   h,     start=180, extent=90,  style="pieslice", **kw)
                np_cvs.create_arc(w-2*r, h-2*r, w,     h,     start=270, extent=90,  style="pieslice", **kw)
                np_cvs.create_rectangle(r, 0,   w-r, h,   **kw)
                np_cvs.create_rectangle(0, r,   w,   h-r, **kw)
            np_cvs.create_arc(0,     0,     2*r,   2*r,   start=90,  extent=90,  style="arc", outline=BORDER)
            np_cvs.create_arc(w-2*r, 0,     w,     2*r,   start=0,   extent=90,  style="arc", outline=BORDER)
            np_cvs.create_arc(0,     h-2*r, 2*r,   h,     start=180, extent=90,  style="arc", outline=BORDER)
            np_cvs.create_arc(w-2*r, h-2*r, w,     h,     start=270, extent=90,  style="arc", outline=BORDER)
            np_cvs.create_line(r, 0,   w-r, 0,   fill=BORDER)
            np_cvs.create_line(r, h,   w-r, h,   fill=BORDER)
            np_cvs.create_line(0, r,   0,   h-r, fill=BORDER)
            np_cvs.create_line(w, r,   w,   h-r, fill=BORDER)
            np_cvs.create_window(w//2, h//2, window=np_inner, width=w-28, anchor="center")

        np_cvs.bind("<Configure>", lambda e: _draw_np(e))
        np_outer.after(10, _draw_np)

        log_outer = tk.Frame(self, bg=BG)
        log_outer.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        tk.Label(log_outer, text="LOG", font=("Segoe UI", 7, "bold"),
                 bg=BG, fg=TEXT_DIM).pack(anchor="w", pady=(0, 4))

        self._log = tk.Text(
            log_outer, height=5, bg=PANEL, fg=TEXT_DIM,
            font=FONT_MONO, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BORDER,
            state="disabled", wrap="word",
        )
        self._log.pack(fill="both", expand=True)

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        self._btn_auth = self._make_btn(btn_frame, "Spotify Authorization", self._do_auth, PURPLE, PURPLE_LT)
        self._btn_auth.pack(side="left", padx=(3, 8))

        self._btn_start = self._make_btn(btn_frame, "Start", self._do_start, GREEN, GREEN_DIM, state="disabled")
        self._btn_start.pack(side="left", padx=(0, 8))

        self._btn_stop = self._make_btn(btn_frame, "Stop", self._do_stop, RED, "#a03434", state="disabled")
        self._btn_stop.pack(side="left")

    def _build_section(self, parent, title, builder_fn):
        section = tk.Frame(parent, bg=BG)
        section.pack(fill="x", pady=(0, 12))

        tk.Label(section, text=title, font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=TEXT_DIM).pack(anchor="w", pady=(0, 5))

        RADIUS = 10
        card_holder = tk.Frame(section, bg=BG)
        card_holder.pack(fill="x")

        cvs = tk.Canvas(card_holder, bg=BG, highlightthickness=0, bd=0)
        cvs.pack(fill="x")

        inner_frame = tk.Frame(cvs, bg=CARD)
        builder_fn(inner_frame)

        def _draw_card(event=None):
            cvs.delete("bg_card")
            w = cvs.winfo_width()
            h = cvs.winfo_height()
            if w < 2 or h < 2:
                return
            r = RADIUS
            for tag, kw in [("bg_card", {"fill": CARD, "outline": ""})]:
                cvs.create_arc(0,     0,     2*r,   2*r,   start=90,  extent=90,  style="pieslice", tags=tag, **kw)
                cvs.create_arc(w-2*r, 0,     w,     2*r,   start=0,   extent=90,  style="pieslice", tags=tag, **kw)
                cvs.create_arc(0,     h-2*r, 2*r,   h,     start=180, extent=90,  style="pieslice", tags=tag, **kw)
                cvs.create_arc(w-2*r, h-2*r, w,     h,     start=270, extent=90,  style="pieslice", tags=tag, **kw)
                cvs.create_rectangle(r, 0,   w-r, h,     tags=tag, **kw)
                cvs.create_rectangle(0, r,   w,   h-r,   tags=tag, **kw)
            cvs.create_arc(0,     0,     2*r,   2*r,   start=90,  extent=90,  style="arc", outline=BORDER, tags="bg_card")
            cvs.create_arc(w-2*r, 0,     w,     2*r,   start=0,   extent=90,  style="arc", outline=BORDER, tags="bg_card")
            cvs.create_arc(0,     h-2*r, 2*r,   h,     start=180, extent=90,  style="arc", outline=BORDER, tags="bg_card")
            cvs.create_arc(w-2*r, h-2*r, w,     h,     start=270, extent=90,  style="arc", outline=BORDER, tags="bg_card")
            cvs.create_line(r,   0,   w-r, 0,   fill=BORDER, tags="bg_card")
            cvs.create_line(r,   h,   w-r, h,   fill=BORDER, tags="bg_card")
            cvs.create_line(0,   r,   0,   h-r, fill=BORDER, tags="bg_card")
            cvs.create_line(w,   r,   w,   h-r, fill=BORDER, tags="bg_card")
            cvs.tag_lower("bg_card")

        def _place_inner(event=None):
            inner_frame.update_idletasks()
            iw = inner_frame.winfo_reqwidth()
            ih = inner_frame.winfo_reqheight()
            total_h = ih + 24 
            cvs.config(height=total_h)
            cvs_w = cvs.winfo_width() if cvs.winfo_width() > 1 else card_holder.winfo_reqwidth()
            cvs.create_window(cvs_w // 2, total_h // 2,
                              window=inner_frame, width=cvs_w - 28,
                              anchor="center", tags="inner_win")
            _draw_card()

        def _on_configure(event):
            cvs.delete("inner_win")
            inner_frame.update_idletasks()
            ih = inner_frame.winfo_reqheight()
            total_h = ih + 24
            cvs.config(height=total_h)
            cvs.create_window(event.width // 2, total_h // 2,
                              window=inner_frame, width=event.width - 28,
                              anchor="center", tags="inner_win")
            _draw_card()

        cvs.bind("<Configure>", _on_configure)
        section.after(10, _place_inner)

    def _build_spotify_fields(self, parent):
        row1 = tk.Frame(parent, bg=CARD)
        row1.pack(fill="x", pady=(0, 8))
        tk.Label(row1, text="Client ID", font=FONT_LABEL, bg=CARD, fg=TEXT_DIM, width=14, anchor="w").pack(side="left")
        self._sp_id = StyledEntry(row1, width=36)
        self._sp_id.pack(side="left", fill="x", expand=True)

        row2 = tk.Frame(parent, bg=CARD)
        row2.pack(fill="x")
        tk.Label(row2, text="Client Secret", font=FONT_LABEL, bg=CARD, fg=TEXT_DIM, width=14, anchor="w").pack(side="left")
        self._sp_secret = StyledEntry(row2, show="•", width=36)
        self._sp_secret.pack(side="left", fill="x", expand=True)

    def _build_slack_fields(self, parent):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x")
        tk.Label(row, text="xoxp- token", font=FONT_LABEL, bg=CARD, fg=TEXT_DIM, width=14, anchor="w").pack(side="left")
        self._slack_tok = StyledEntry(row, show="•", width=36)
        self._slack_tok.pack(side="left", fill="x", expand=True)

    def _build_settings_fields(self, parent):
        row1 = tk.Frame(parent, bg=CARD)
        row1.pack(fill="x", pady=(0, 8))
        tk.Label(row1, text="Emoji status", font=FONT_LABEL, bg=CARD, fg=TEXT_DIM, width=14, anchor="w").pack(side="left")
        self._emoji = StyledEntry(row1, width=14)
        self._emoji.set(":spotify_logo:")
        self._emoji.pack(side="left")

        row2 = tk.Frame(parent, bg=CARD)
        row2.pack(fill="x")
        tk.Label(row2, text="Interval (sec)", font=FONT_LABEL, bg=CARD, fg=TEXT_DIM, width=14, anchor="w").pack(side="left")
        self._interval = StyledEntry(row2, width=6)
        self._interval.set("1")
        self._interval.pack(side="left")

    def _load_saved_config(self):
        cfg = load_config()
        if cfg.get("sp_id"):      self._sp_id.set(cfg["sp_id"])
        if cfg.get("sp_secret"):  self._sp_secret.set(cfg["sp_secret"])
        if cfg.get("slack_tok"):  self._slack_tok.set(cfg["slack_tok"])
        if cfg.get("emoji"):      self._emoji.set(cfg["emoji"])
        if cfg.get("interval"):   self._interval.set(cfg["interval"])

    def _save_config(self):
        save_config({
            "sp_id":     self._sp_id.get().strip(),
            "sp_secret": self._sp_secret.get().strip(),
            "slack_tok": self._slack_tok.get().strip(),
            "emoji":     self._emoji.get().strip(),
            "interval":  self._interval.get().strip(),
        })

    def _on_close(self):
        self._save_config()
        self.destroy()

    def _make_btn(self, parent, text, cmd, color, hover_color, state="normal"):
        R = 8
        PAD_X, PAD_Y = 14, 8
        FONT = ("Segoe UI", 9, "bold")

        import tkinter.font as tkfont
        f = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        tw = f.measure(text)
        th = f.metrics("linespace")
        w = tw + PAD_X * 2
        h = th + PAD_Y * 2

        cvs = tk.Canvas(parent, width=w, height=h,
                        highlightthickness=0, bd=0, bg=BG, cursor="hand2")

        cvs._enabled    = (state != "disabled")
        cvs._color      = color if cvs._enabled else BORDER
        cvs._hover_color = hover_color
        cvs._text_color = "white" if cvs._enabled else TEXT_DIM
        cvs._cmd        = cmd
        cvs._r          = R
        cvs._label_text = text

        def _redraw(c=None):
            cvs.delete("all")
            bg_c = c if c else cvs._color
            r = cvs._r
            cw, ch = int(cvs["width"]), int(cvs["height"])
            cvs.create_arc(0,      0,      2*r,    2*r,    start=90,  extent=90,  fill=bg_c, outline="")
            cvs.create_arc(cw-2*r, 0,      cw,     2*r,    start=0,   extent=90,  fill=bg_c, outline="")
            cvs.create_arc(0,      ch-2*r, 2*r,    ch,     start=180, extent=90,  fill=bg_c, outline="")
            cvs.create_arc(cw-2*r, ch-2*r, cw,     ch,     start=270, extent=90,  fill=bg_c, outline="")
            cvs.create_rectangle(r, 0,      cw-r, ch,     fill=bg_c, outline="")
            cvs.create_rectangle(0, r,      cw,   ch-r,   fill=bg_c, outline="")
            cvs.create_text(cw//2, ch//2, text=cvs._label_text,
                            font=FONT, fill=cvs._text_color)

        cvs._redraw = _redraw
        _redraw()

        def on_enter(_):
            if cvs._enabled:
                _redraw(cvs._hover_color)

        def on_leave(_):
            if cvs._enabled:
                _redraw(cvs._color)

        def on_click(_):
            if cvs._enabled:
                cmd()

        cvs.bind("<Enter>",    on_enter)
        cvs.bind("<Leave>",    on_leave)
        cvs.bind("<Button-1>", on_click)
        return cvs

    def _enable_btn(self, btn, color, hover):
        btn._enabled     = True
        btn._color       = color
        btn._hover_color = hover
        btn._text_color  = "white"
        btn.config(cursor="hand2")
        btn._redraw()

    def _disable_btn(self, btn):
        btn._enabled    = False
        btn._color      = BORDER
        btn._text_color = TEXT_DIM
        btn.config(cursor="arrow")
        btn._redraw()

    def _update_status(self, text, color, pulse=False):
        self._status_lbl.config(text=text, fg=color)
        if pulse:
            self._dot.set_color(color, pulse=True)
        else:
            self._dot.stop()
            self._dot.set_color(color)

    def _log_msg(self, text):
        self._log.config(state="normal")
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log.insert("end", f"[{ts}] {text}\n")
        self._log.see("end")
        self._log.config(state="disabled")

    def _set_now_playing(self, text):
        self._np_lbl.config(text=text if text else "-", fg=GREEN if text else TEXT_DIM)

    def _do_auth(self):
        global auth_code
        cid = self._sp_id.get().strip()
        sec = self._sp_secret.get().strip()
        if not cid or not sec:
            messagebox.showerror("Error!", "Fill in your Spotify Client ID and Client Secret.")
            return

        auth_code = None
        self._update_status("Waiting for Spotify authorization...", AMBER, pulse=True)
        self._log_msg("Open the browser for Spotify authorisation...")

        def do_auth_thread():
            global auth_code, access_token, refresh_token
            try:
                get_auth_code(cid)
                if not auth_code:
                    self.after(0, lambda: self._update_status("Authorization failed", RED))
                    self.after(0, lambda: self._log_msg("Authorization code not received"))
                    return
                tokens = get_tokens(auth_code, cid, sec)
                access_token  = tokens.get("access_token")
                refresh_token = tokens.get("refresh_token")
                if not access_token:
                    self.after(0, lambda: self._update_status("Invalid Token", RED))
                    self.after(0, lambda: self._log_msg(f"Token Error : {tokens}"))
                    return
                self.after(0, lambda: self._update_status("Authorized", GREEN))
                self.after(0, lambda: self._log_msg("Spotify authorization successful!"))
                self.after(0, lambda: self._enable_btn(self._btn_start, GREEN, GREEN_DIM))
            except Exception as e:
                self.after(0, lambda: self._log_msg(f"Auth Error: {e}"))
                self.after(0, lambda: self._update_status("Error", RED))

        threading.Thread(target=do_auth_thread, daemon=True).start()

    def _do_start(self):
        global running, worker_thread
        if running:
            return
        running = True
        self._disable_btn(self._btn_start)
        self._enable_btn(self._btn_stop, RED, "#a03434")
        self._update_status("Running - Spotify Playback", GREEN, pulse=True)
        self._log_msg("Running...")
        worker_thread = threading.Thread(target=self._worker, daemon=True)
        worker_thread.start()

    def _do_stop(self):
        global running
        running = False
        slack_tok = self._slack_tok.get().strip()
        if slack_tok and access_token:
            try:
                set_slack_status("", "", slack_tok)
            except Exception:
                pass
        self._disable_btn(self._btn_stop)
        self._enable_btn(self._btn_start, GREEN, GREEN_DIM)
        self._update_status("Stopped", TEXT_DIM)
        self._set_now_playing(None)
        self._log_msg("Stopped. Slack status deleted!")

    def _worker(self):
        global running, access_token
        cid     = self._sp_id.get().strip()
        sec     = self._sp_secret.get().strip()
        slack   = self._slack_tok.get().strip()
        emoji   = self._emoji.get().strip() or ":spotify_logo:"
        try:
            interval = float(self._interval.get().strip())
        except ValueError:
            interval = 1.0

        last_track    = None
        refresh_count = 0
        refresh_every = int(3000 / max(interval, 0.5))

        while running:
            try:
                if refresh_count >= refresh_every:
                    new_tok = refresh_access_token_fn(refresh_token, cid, sec)
                    if new_tok:
                        access_token = new_tok
                        self.after(0, lambda: self._log_msg("Spotify token renewed"))
                    refresh_count = 0

                current = get_current_track(access_token)
                current_name = current.rsplit(" : ", 1)[0] if current else None

                if current_name != last_track:
                    if current:
                        self.after(0, lambda c=current: self._set_now_playing(c))
                        self.after(0, lambda c=current: self._log_msg(f"Playback: {c}"))
                        set_slack_status(current, emoji, slack)
                    else:
                        self.after(0, lambda: self._set_now_playing(None))
                        self.after(0, lambda: self._log_msg("Nothing playing - status deleted!"))
                        set_slack_status("", "", slack)
                    last_track = current_name
                elif current:
                    set_slack_status(current, emoji, slack)
                    self.after(0, lambda c=current: self._set_now_playing(c))

                refresh_count += 1
                time.sleep(interval)

            except Exception as e:
                self.after(0, lambda err=e: self._log_msg(f"Err: {err}"))
                time.sleep(5)

if __name__ == "__main__":
    app = App()
    app.deiconify()
    app.mainloop()
