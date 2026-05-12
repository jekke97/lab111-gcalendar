"""
Run this once to get a refresh token and save credentials to .env
You need CLIENT_ID and CLIENT_SECRET from Google Cloud Console:
  https://console.cloud.google.com/apis/credentials
"""
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

CLIENT_ID     = input("Paste CLIENT_ID: ").strip()
CLIENT_SECRET = input("Paste CLIENT_SECRET: ").strip()

CLIENT_CONFIG = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uris": ["http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

SCOPES = ['https://www.googleapis.com/auth/calendar']
flow   = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
creds  = flow.run_local_server(port=0)

env = Path(__file__).parent / ".env"
env.write_text(
    f"CLIENT_ID={CLIENT_ID}\n"
    f"CLIENT_SECRET={CLIENT_SECRET}\n"
    f"REFRESH_TOKEN={creds.refresh_token}\n"
)
print(f"\nSaved to {env}")
