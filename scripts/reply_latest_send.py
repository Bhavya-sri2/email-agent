# scripts/reply_latest_send.py
from __future__ import annotations

import base64
from email.mime.text import MIMEText
from email.utils import parseaddr

from app.gmail_client import get_gmail_service
from app.local_llm import generate_reply


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _extract_text_plain(payload: dict) -> str:
    """
    Extract the text/plain body from a Gmail 'full' message payload.
    Falls back to text/html stripped-ish if needed.
    """
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {}) or {}
    data = body.get("data")

    if mime_type == "text/plain" and data:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

    # Multipart: walk parts
    parts = payload.get("parts", []) or []
    if parts:
        # First try text/plain
        for p in parts:
            text = _extract_text_plain(p)
            if text.strip():
                return text

        # If no plain found, try html and do a basic strip
        for p in parts:
            if p.get("mimeType") == "text/html":
                d = (p.get("body") or {}).get("data")
                if d:
                    html = base64.urlsafe_b64decode(d.encode("utf-8")).decode("utf-8", errors="replace")
                    # very basic cleanup (no external deps)
                    return (
                        html.replace("<br>", "\n")
                            .replace("<br/>", "\n")
                            .replace("<br />", "\n")
                    )

    # Single-part but not plain (rare)
    if data:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

    return ""


def _make_raw_email(
    to_addr: str,
    from_addr: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> str:
    msg = MIMEText(body, _charset="utf-8")
    msg["To"] = to_addr
    msg["From"] = from_addr
    msg["Subject"] = subject

    # These help Gmail thread the reply correctly
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return raw


def main():
    service = get_gmail_service()

    # 1) Get the newest unread email in inbox that is NOT from you
    results = service.users().messages().list(
        userId="me",
        q="is:unread in:inbox -from:me",
        maxResults=1,
    ).execute()

    msgs = results.get("messages", [])
    if not msgs:
        print("No unread emails found. Nothing to reply to.")
        return

    msg_id = msgs[0]["id"]

    # 2) Fetch full message so we can get headers + body
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    payload = msg.get("payload", {}) or {}
    headers = payload.get("headers", []) or []

    from_raw = _get_header(headers, "From")
    subject = _get_header(headers, "Subject")
    message_id = _get_header(headers, "Message-ID")
    references = _get_header(headers, "References")

    from_name, from_email = parseaddr(from_raw)
    if not from_email:
        print("Could not parse sender email. Aborting.")
        return

    body_text = _extract_text_plain(payload).strip()
    if not body_text:
        body_text = "(No readable body found)"

    # 3) Generate a real reply using sender + subject + BODY
    llm_result = generate_reply(email_from=from_raw, subject=subject, body=body_text)
    reply_text = llm_result.text.strip()

    # 4) Send reply
    profile = service.users().getProfile(userId="me").execute()
    my_email = profile.get("emailAddress")

    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

    raw = _make_raw_email(
        to_addr=from_email,
        from_addr=my_email,
        subject=reply_subject,
        body=reply_text,
        in_reply_to=message_id or None,
        references=references or None,
    )

    sent = service.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": msg.get("threadId")},
    ).execute()

    # 5) Mark original as read so we don't reply again
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()

    extra = ""
    if getattr(llm_result, "used_fallback", False):
        extra = " (LLM fallback used)"

    print(f"✅ Replied & sent. Sent message id: {sent.get('id')}{extra}")


if __name__ == "__main__":
    main()


