from __future__ import annotations

import base64
import re
import sys
from pathlib import Path
from email.mime.text import MIMEText

# --- Make sure we can import from project root when running "py -m scripts.reply_latest_draft"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.gmail_client import get_gmail_service
from app.local_llm import generate_reply


def extract_text(payload: dict) -> str:
    """
    Prefer text/plain from Gmail payload. Fallback to decoding single-body.
    """
    if not payload:
        return ""

    # Single-part body
    if "parts" not in payload:
        data = payload.get("body", {}).get("data")
        if not data:
            return ""
        try:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        except Exception:
            return ""

    # Multi-part: walk parts recursively; prefer text/plain
    def walk(parts: list[dict]) -> str:
        for part in parts:
            mime = part.get("mimeType", "")
            body = part.get("body", {}) or {}

            if mime == "text/plain":
                data = body.get("data")
                if data:
                    try:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    except Exception:
                        pass

            # nested multipart
            if part.get("parts"):
                t = walk(part["parts"])
                if t:
                    return t

        return ""

    return walk(payload.get("parts", []))


def get_header(headers: list[dict], name: str) -> str:
    for h in headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "") or ""
    return ""


def clean_subject(subj: str) -> str:
    subj = (subj or "").strip()
    if not subj:
        return "Re: (no subject)"
    if subj.lower().startswith("re:"):
        return subj
    return f"Re: {subj}"


def extract_email_address(from_header: str) -> str:
    """
    From: 'Name <email@x.com>' -> 'email@x.com'
    """
    if not from_header:
        return ""
    m = re.search(r"<([^>]+)>", from_header)
    return m.group(1).strip() if m else from_header.strip()


def build_prompt(from_addr: str, subject: str, email_text: str) -> str:
    return f"""
You are an email reply assistant.

Write a reply email to the sender in a natural, professional tone.

Rules:
- Do NOT say “How can I help?” / “How may I assist you?”
- Do NOT invent details
- Do NOT confirm payment unless the email explicitly says payment was made
- If the email is unclear, ask ONE short clarifying question
- Do NOT mention you are an AI
- Keep it concise and human

From: {from_addr}
Subject: {subject}

Email content:
{email_text}

Return ONLY the email body.
Sign off exactly as:
Bhavyasri
""".strip()


def create_gmail_draft_reply(service, to_email: str, subject: str, body: str, thread_id: str | None):
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to_email
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    draft_body = {"message": {"raw": raw}}
    if thread_id:
        draft_body["message"]["threadId"] = thread_id

    draft = service.users().drafts().create(userId="me", body=draft_body).execute()
    return draft


def main():
    service = get_gmail_service()

    # OPTION A: latest UNREAD only (recommended)
    # query = "in:inbox is:unread"
    #
    # OPTION B: latest in inbox (read or unread)
    query = "in:inbox"

    results = service.users().messages().list(userId="me", q=query, maxResults=1).execute()
    msgs = results.get("messages", [])

    if not msgs:
        print("No messages found.")
        return

    msg_id = msgs[0]["id"]
    full = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

    payload = full.get("payload", {}) or {}
    headers = payload.get("headers", []) or []

    from_header = get_header(headers, "From")
    subject = get_header(headers, "Subject")
    thread_id = full.get("threadId")

    email_text = extract_text(payload).strip()
    if not email_text:
        email_text = (full.get("snippet") or "").strip()

    to_email = extract_email_address(from_header)
    reply_subject = clean_subject(subject)

    prompt = build_prompt(from_header, subject, email_text)
    llm_reply = generate_reply(prompt).strip()

    draft = create_gmail_draft_reply(
        service=service,
        to_email=to_email,
        subject=reply_subject,
        body=llm_reply,
        thread_id=thread_id,
    )

    print(f"✅ Draft created: {draft.get('id')}")
    print("\n--- Reply preview ---\n")
    print(llm_reply)


if __name__ == "__main__":
    main()
