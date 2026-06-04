"""
tools/linkedin_auth.py
──────────────────────
One-time script to authorize your LinkedIn app and capture
your access token + refresh token for GitHub Secrets.

Usage:
    python tools/linkedin_auth.py

You'll need:
  - Your LinkedIn App's Client ID
  - Your LinkedIn App's Client Secret
  (both found on the Auth tab of your app at developer.linkedin.com)

What it does:
  1. Starts a tiny local web server on port 8000
  2. Opens your browser to LinkedIn's authorization page
  3. You log in and approve the permissions
  4. LinkedIn redirects back to localhost:8000 with an auth code
  5. The script exchanges the code for tokens and prints them out
  6. Copy the tokens into GitHub Secrets
"""

import http.server
import threading
import webbrowser
import urllib.parse
import urllib.request
import json
import sys
import os

# ── CONFIG — fill these in before running ─────────────────────────────────────
CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI  = "http://localhost:8000/callback"
SCOPE         = "w_member_social openid profile email"
# ──────────────────────────────────────────────────────────────────────────────

auth_code = None


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/callback":
            params = urllib.parse.parse_qs(parsed.query)

            if "error" in params:
                error = params["error"][0]
                desc  = params.get("error_description", ["Unknown error"])[0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"""
                <html><body style="font-family:sans-serif;padding:40px;background:#0a0f1e;color:#ef4444">
                <h2>Authorization Failed</h2>
                <p><strong>{error}</strong>: {desc}</p>
                <p>Close this window and check the terminal for details.</p>
                </body></html>""".encode())
                print(f"\n❌ Authorization failed: {error} — {desc}")
                return

            if "code" in params:
                auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                <html><body style="font-family:sans-serif;padding:40px;background:#0a0f1e;color:#00c896">
                <h2 style="color:#00c896">&#x2705; Authorization successful!</h2>
                <p style="color:#e2e8f0">You can close this window and go back to the terminal.</p>
                </body></html>""")
                print("\n✅ Authorization code received!")
                # Signal server to stop
                threading.Thread(target=self.server.shutdown).start()

    def log_message(self, format, *args):
        pass  # Suppress request logs


def exchange_code_for_token(code: str) -> dict:
    """Exchange the authorization code for access + refresh tokens."""
    data = urllib.parse.urlencode({
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode()

    req = urllib.request.Request(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_person_urn(access_token: str) -> str:
    """Fetch your LinkedIn person URN (needed if posting as a person)."""
    req = urllib.request.Request(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        return data.get("sub", "")  # sub is the person ID


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ CLIENT_ID and CLIENT_SECRET must be set.")
        print("   Run with:")
        print("   LINKEDIN_CLIENT_ID=xxx LINKEDIN_CLIENT_SECRET=yyy python tools/linkedin_auth.py")
        sys.exit(1)

    # Build the authorization URL
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode({
            "response_type": "code",
            "client_id":     CLIENT_ID,
            "redirect_uri":  REDIRECT_URI,
            "scope":         SCOPE,
            "state":         "aidevdefense_auth",
        })
    )

    print("\n" + "=" * 60)
    print("  AI Dev Defense — LinkedIn OAuth Token Fetcher")
    print("=" * 60)
    print("\n📋 Make sure http://localhost:8000/callback is added as an")
    print("   Authorized Redirect URL in your LinkedIn app's Auth tab.")
    print("\n🌐 Opening browser for LinkedIn authorization...")
    print(f"\n   If it doesn't open automatically, visit:\n   {auth_url}\n")

    # Start local callback server
    server = http.server.HTTPServer(("localhost", 8000), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    server_thread.join()

    if not auth_code:
        print("❌ No authorization code received. Exiting.")
        sys.exit(1)

    # Exchange code for tokens
    print("\n🔄 Exchanging authorization code for tokens...")
    try:
        tokens = exchange_code_for_token(auth_code)
    except Exception as e:
        print(f"❌ Token exchange failed: {e}")
        sys.exit(1)

    access_token  = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    expires_in    = tokens.get("expires_in", 0)

    # Fetch person URN
    print("🔍 Fetching your LinkedIn Person URN...")
    try:
        person_id  = get_person_urn(access_token)
        person_urn = f"urn:li:person:{person_id}"
    except Exception as e:
        person_urn = "Could not fetch — check manually"
        print(f"  ⚠️  Could not fetch person URN: {e}")

    # Print results
    print("\n" + "=" * 60)
    print("  ✅ SUCCESS — Add these to GitHub Secrets")
    print("=" * 60)
    print(f"\n  LINKEDIN_ACCESS_TOKEN")
    print(f"  {access_token}")
    print(f"\n  LINKEDIN_REFRESH_TOKEN")
    print(f"  {refresh_token or '(not provided — LinkedIn may not issue refresh tokens for this scope)'}")
    print(f"\n  LINKEDIN_PERSON_URN")
    print(f"  {person_urn}")
    print(f"\n  Token expires in: {expires_in // 3600} hours ({expires_in // 86400} days)")
    print("\n" + "=" * 60)
    print("\n📋 Also find your Organization URN:")
    print("   Go to your LinkedIn company page URL:")
    print("   https://www.linkedin.com/company/YOUR_COMPANY/")
    print("   The number in the URL IS your org ID.")
    print("   Format it as: urn:li:organization:XXXXXXXX")
    print("   Add that as: LINKEDIN_ORG_URN")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()