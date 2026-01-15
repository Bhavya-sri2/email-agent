from __future__ import annotations

import base64
import re
from email.message import EmailMessage
from typing import Optional

from app.gmail_client import get_gmail_service
from app.local_llm import generate_reply


def _get_header(headers, name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _decode_base64url(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode("utf-8") + b"===").decode("utf-8", errors="replace")


def _extract_text_plain(payload: dict) -> str:
    """
    Prefer text/plain. If not found, fall back to stripping HTML.
    """
    # Direct body
    mime = payload.get("mimeType", "")
    body = payload.get("body", {}) or {}
    data = body.get("data")
    if data and mime == "text/plain":
        return _decode_base64url(data)

    # Parts
    parts = payload.get("parts", []) or []
    text_plain = None
    text_html = None

    def walk(p):
        nonlocal text_plain, text_html
        mt = p.get("mimeType", "")
        b = p.get("body", {}) or {}
        d = b.get("data")

        if d and mt == "text/plain" and text_plain is None:
            text_plain = _decode_base64url(d)
        elif d and mt == "text/html" and text_html is None:
            text_html = _decode_base64url(d)

        for child in p.get("parts", []) or []:
            walk(child)

    for p in parts:
        walk(p)

    if text_plain:
        return text_plain

    if text_html:
        # Very basic HTML strip
        txt = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", "", text_html)
        txt = re.sub(r"(?s)<.*?>", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt

    return ""


def build_prompt(from_name: str, subject: str, email_text: str) -> str:
    return f"""
You are an email assistant. Write a concise, polite reply.

Rules:
- Keep it 4-8 lines max.
- Do NOT invent details.
- If info is missing, ask 1-2 clarifying questions.
- End with a friendly closing.

Context:
From: {from_name}
Subject: {subject}

Email:
{email_text}
""".strip()


def create_reply_draft(service, user_id: str, msg: dict, reply_text: str) -> str:
    headers = msg["payload"]["headers"]
    subject = _get_header(headers, "Subject")
    from_h = _get_header(headers, "From")
    message_id = _get_header(headers, "Message-ID")
    references = _get_header(headers, "References")

    # Make sure subject has Re:
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    email = EmailMessage()
    email["To"] = from_h
    email["Subject"] = subject

    if message_id:
        email["In-Reply-To"] = message_id
        # References should include prior refs + message_id
        if references:
            email["References"] = f"{references} {message_id}"
        else:
            email["References"] = message_id

    email.set_content(reply_text)

    raw = base64.urlsafe_b64encode(email.as_bytes()).decode("utf-8")

    draft_body = {
        "message": {
            "raw": raw,
            "threadId": msg.get("threadId"),
        }
    }

    draft = service.users().drafts().create(userId=user_id, body=draft_body).execute()
    return draft["id"]


def main(max_messages: int = 5):
    service = get_gmail_service()
    user_id = "me"

    # Unread, avoid your own sent mail
    resp = service.users().messages().list(
        userId=user_id,
        q="is:unread -from:me",
        maxResults=max_messages,
    ).execute()

    msgs = resp.get("messages", [])
    if not msgs:
        print("No unread messages found.")
        return

    print(f"Found {len(msgs)} unread messages. Creating drafts...")

    for item in msgs:
        msg_id = item["id"]
        msg = service.users().messages().get(userId=user_id, id=msg_id, format="full").execute()

        headers = msg["payload"]["headers"]
        subject = _get_header(headers, "Subject")
        from_h = _get_header(headers, "From")

        email_text = _extract_text_plain(msg["payload"]).strip()
        if not email_text:
            email_text = (msg.get("snippet") or "").strip()

        prompt = build_prompt(from_h, subject, email_text)
        reply = generate_reply(prompt).strip()

        draft_id = create_reply_draft(service, user_id, msg, reply)
        print(f"✅ Draft created for: {subject} | Draft ID: {draft_id}")

    print("Done.")


if __name__ == "__main__":
    main()
