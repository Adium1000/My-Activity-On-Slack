# _______  _______  _______  _______  ___   _______  __   __    _______  __    _    _______  ___      _______  _______  ___   _ 
#|       ||       ||       ||       ||   | |       ||  | |  |  |       ||  |  | |  |       ||   |    |   _   ||       ||   | | |
#|  _____||    _  ||   _   ||_     _||   | |    ___||  |_|  |  |   _   ||   |_| |  |  _____||   |    |  |_|  ||       ||   |_| |
#| |_____ |   |_| ||  | |  |  |   |  |   | |   |___ |       |  |  | |  ||       |  | |_____ |   |    |       ||       ||      _|
#|_____  ||    ___||  |_|  |  |   |  |   | |    ___||_     _|  |  |_|  ||  _    |  |_____  ||   |___ |       ||      _||     |_ 
# _____| ||   |    |       |  |   |  |   | |   |      |   |    |       || | |   |   _____| ||       ||   _   ||     |_ |    _  |
#|_______||___|    |_______|  |___|  |___| |___|      |___|    |_______||_|  |__|  |_______||_______||__| |__||_______||___| |_|

print("Spotify on Slack: Terminal Version : v1.2 : By Adrian")
print("")
print("Loading...")
import time
import requests
import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode

# ============================================================
# IDs and Tokens
# ============================================================
SPOTIFY_CLIENT_ID     = ""
SPOTIFY_CLIENT_SECRET = ""
SLACK_TOKEN           = ""   # xoxp-...
# ============================================================

SPOTIFY_REDIRECT_URI  = "http://127.0.0.1:9090/callback"
SPOTIFY_SCOPE         = "user-read-currently-playing user-read-playback-state"

auth_code = None

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
    def log_message(self, format, *args):
        pass

def get_auth_code():
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SPOTIFY_SCOPE,
    }
    url = "https://accounts.spotify.com/authorize?" + urlencode(params)
    print("Spotify Auth")
    webbrowser.open(url)
    server = HTTPServer(("127.0.0.1", 9090), CallbackHandler)
    server.handle_request()

def get_tokens(code):
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
        },
        auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
    )
    return resp.json()

def refresh_access_token(refresh_token):
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
    )
    return resp.json().get("access_token")

def format_ms(ms):
    total_sec = ms // 1000
    minutes = total_sec // 60
    seconds = total_sec % 60
    return f"{minutes}:{seconds:02d}"

def get_current_track(access_token):
    resp = requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if resp.status_code == 200 and resp.content:
        data = resp.json()
        if data.get("is_playing") and data.get("item"):
            track = data["item"]["name"]
            artist = data["item"]["artists"][0]["name"]
            elapsed = format_ms(data.get("progress_ms", 0))
            duration = format_ms(data["item"]["duration_ms"])
            return f"{artist} - {track} : {elapsed}/{duration}"
    return None

def set_slack_status(text, emoji=":spotify_logo:"):
    profile = {
        "status_text": text if text else "",
        "status_emoji": emoji if text else "",
        "status_expiration": 0,
    }
    requests.post(
        "https://slack.com/api/users.profile.set",
        headers={
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json",
        },
        data=json.dumps({"profile": profile}),
    )


def main():
    get_auth_code()
    if not auth_code:
        print("Error: Authorization code not received.")
        return

    tokens = get_tokens(auth_code)
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if not access_token:
        print("Error:Spotify token not received.", tokens)
        return

    print("Done\n")

    last_track_name = None
    token_refresh_counter = 0

    while True:
        try:
            if token_refresh_counter >= 600: 
                access_token = refresh_access_token(refresh_token)
                token_refresh_counter = 0
                print("Reloaded Spotify Token")

            current = get_current_track(access_token)
            current_name = current.rsplit(" : ", 1)[0] if current else None

            if current_name != last_track_name:
                if current:
                    print(f"you listen to: {current}")
                    set_slack_status(current)
                else:
                    print("You don't listen to any music, deleting Slack Status...")
                    set_slack_status("")
                last_track_name = current_name
            elif current:
                set_slack_status(current)

            token_refresh_counter += 1
            time.sleep(1)

        except KeyboardInterrupt:
            print("\nDeleting Slack Status...")
            set_slack_status("")
            break
        except Exception as e:
            print(f"Err : {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
