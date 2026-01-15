from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.gmail_client import get_gmail_service  # noqa: E402
from app.db import insert_email, email_exists  # noqa: E402


def parse_from_and_subject(msg_detail: dict):
    headers = msg_detail.get("payload", {}).get("headers", [])
    h = {x["name"].lower(): x["value"] for x in headers if "name" in x and "value" in x}
    sender = h.get("from", "")
    subject = h.get("subject", "")
    return sender, subject


def main():
    service = get_gmail_service()

    res = service.users().messages().list(userId="me", maxResults=10, q="in:inbox").execute()
    messages = res.get("messages", [])

    print(f"Found {len(messages)} messages (latest 10 in inbox)")

    new_count = 0
    for m in messages:
        gmail_id = m["id"]

        if email_exists(gmail_id):
            continue

        msg_detail = service.users().messages().get(
            userId="me",
            id=gmail_id,
            format="metadata",
            metadataHeaders=["From", "Subject"],
        ).execute()

        sender, subject = parse_from_and_subject(msg_detail)
        insert_email(gmail_id, sender, subject)

        new_count += 1
        print(f"Logged ✅ {gmail_id} | {sender} | {subject}")

    print(f"Done. New emails logged: {new_count}")


if __name__ == "__main__":
    main()
