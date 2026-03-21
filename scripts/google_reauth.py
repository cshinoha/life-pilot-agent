#!/usr/bin/env python3
"""Google Calendar OAuth re-auth script. Run interactively."""

import json
import os
import sys

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "..", "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "token.json")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def main() -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import]
    except ImportError:
        print("Installing google-auth-oauthlib...")
        os.system(f"{sys.executable} -m pip install google-auth-oauthlib -q")
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import]

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES)

    # Generate URL manually (no local server needed on VPS)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

    print("\n=== Google Calendar Re-Auth ===")
    print("\n1. Открой эту ссылку в браузере:\n")
    print(auth_url)
    print("\n2. Войди в Google, разреши доступ к Calendar.")
    print("3. Скопируй код со страницы и вставь сюда.\n")

    code = input("Код: ").strip()

    flow.fetch_token(code=code)
    creds = flow.credentials

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"\n✓ token.json обновлён: {os.path.abspath(TOKEN_FILE)}")
    print("Перезапусти бота: systemctl restart d-brain.service")


if __name__ == "__main__":
    main()
