"""
One-time Spotify OAuth setup script.
Run this once to authorize the bot to read your playlists.
It will save a refresh token to your .env file so the bot
can fetch full playlists (all tracks, not just the first 100).

Before running, make sure your Spotify app has this Redirect URI:
    http://127.0.0.1:8888/callback

Usage:
    python spotify_auth.py
"""
import os
import base64
import webbrowser
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
from dotenv import load_dotenv, set_key

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "playlist-read-private playlist-read-collaborative"
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

# Shared state to pass the code out of the HTTP handler
_auth_code = None


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "error" in params:
            _auth_code = None
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Authorization denied. You can close this tab.</h2>")
        elif "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Authorization successful! You can close this tab and return to the terminal.</h2>")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Silence request logs


def main():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("ERROR: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env")
        return

    params = urlencode({
        "response_type": "code",
        "client_id": SPOTIFY_CLIENT_ID,
        "scope": SCOPE,
        "redirect_uri": REDIRECT_URI,
    })
    auth_url = f"https://accounts.spotify.com/authorize?{params}"

    print("=" * 60)
    print("SPOTIFY BOT AUTHORIZATION")
    print("=" * 60)
    print()
    print("Make sure your Spotify app has this Redirect URI registered:")
    print(f"  {REDIRECT_URI}")
    print()
    print("Opening your browser. Click 'Agree' to authorize...")
    print()

    # Start the local callback server
    server = HTTPServer(("127.0.0.1", 8888), _CallbackHandler)
    server.timeout = 120  # 2 minute timeout

    webbrowser.open(auth_url)

    # Wait for one request (the callback)
    server.handle_request()
    server.server_close()

    if not _auth_code:
        print("ERROR: Authorization was denied or timed out.")
        return

    # Exchange the code for tokens
    creds = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": _auth_code,
            "redirect_uri": REDIRECT_URI,
        },
    )

    if resp.status_code != 200:
        print(f"ERROR: Token exchange failed ({resp.status_code}): {resp.text}")
        return

    refresh_token = resp.json().get("refresh_token")
    if not refresh_token:
        print("ERROR: No refresh_token in response:", resp.json())
        return

    set_key(ENV_FILE, "SPOTIFY_REFRESH_TOKEN", refresh_token)

    print("=" * 60)
    print("SUCCESS! Refresh token saved to .env")
    print("=" * 60)
    print()
    print("The bot will now load full Spotify playlists.")
    print("You do NOT need to run this script again unless you revoke access.")


if __name__ == "__main__":
    main()

