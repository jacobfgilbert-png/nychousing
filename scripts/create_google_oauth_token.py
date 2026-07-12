from __future__ import annotations

import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create authorized-user Google OAuth JSON for GitHub Actions secrets.")
    parser.add_argument("client_secret_json")
    parser.add_argument("--output", default="google_authorized_user.json")
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret_json, scopes=SCOPES)
    credentials = flow.run_local_server(port=0, open_browser=True)
    output = Path(args.output)
    output.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Wrote authorized-user JSON to {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
