from __future__ import annotations

from app.gmail_client import get_gmail_service


def main():
    service = get_gmail_service()

    # Get profile (confirms token + scope)
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress")

    # List messages
    results = service.users().messages().list(
        userId="me",
        maxResults=20
    ).execute()

    messages = results.get("messages", [])

    # Count threads
    threads = service.users().threads().list(userId="me").execute()
    thread_count = len(threads.get("threads", []))

    # Unread count
    unread = service.users().messages().list(
        userId="me",
        q="is:unread"
    ).execute()

    unread_count = unread.get("resultSizeEstimate", 0)

    print("✅ Gmail connected")
    print(f"Email: {email}")
    print(f"Total messages: {len(messages)} | Total threads: {thread_count}")
    print(f"Unread estimate: {unread_count}")


if __name__ == "__main__":
    main()
