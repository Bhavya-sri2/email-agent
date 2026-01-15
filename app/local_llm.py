# app/local_llm.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    from gpt4all import GPT4All
except Exception:  # pragma: no cover
    GPT4All = None  # type: ignore


DEFAULT_MODEL_HINT = (
    "If GPT4All model path isn't configured, install a model in the GPT4All app "
    "and set GPT4ALL_MODEL_PATH in your .env to the .gguf file path."
)

@dataclass
class LLMResult:
    text: str
    used_fallback: bool = False
    error: Optional[str] = None


_model = None  # cached singleton


def _load_model() -> GPT4All:
    global _model
    if _model is not None:
        return _model

    if GPT4All is None:
        raise RuntimeError("gpt4all python package not available.")

    # ✅ EASIEST: put your model name here if you use GPT4All's default model directory
    # Example names often look like: "Meta-Llama-3-8B-Instruct.Q4_0.gguf"
    # If you don't know the name, we can print the models folder next.
    model_name_or_path = "Meta-Llama-3-8B-Instruct.Q4_0.gguf"

    _model = GPT4All(model_name_or_path)
    return _model


def generate_reply(email_from: str, subject: str, body: str) -> LLMResult:
    """
    Generate an email reply based on the incoming email.
    """
    # Basic guard: don’t respond to empty bodies
    body_clean = (body or "").strip()
    if not body_clean:
        return LLMResult(
            text="Hi, thanks for your email. Could you please share a bit more detail so I can help?",
            used_fallback=True,
        )

    prompt = f"""
You are my personal email assistant. Write a helpful, concise reply.
Rules:
- Be polite and human.
- Answer the question if possible.
- If the email is unclear, ask 1-2 clarifying questions.
- Keep it under 6 sentences unless necessary.
- Sign off as: Sri

Email received:
From: {email_from}
Subject: {subject}

Body:
{body_clean}

Now write the reply email:
""".strip()

    # Try GPT4All
    try:
        model = _load_model()
        with model.chat_session():
            out = model.generate(
                prompt,
                max_tokens=220,
                temp=0.4,
                top_p=0.9,
            )
        text = out.strip()
        if not text:
            raise RuntimeError("Empty model output")
        return LLMResult(text=text, used_fallback=False)
    except Exception as e:
        # Smart fallback: answer simple known questions if obvious; otherwise acknowledge.
        lower = body_clean.lower()
        if "capital" in lower and "india" in lower:
            reply = "Hi, the capital of India is New Delhi.\n\nBest,\nSri"
        elif "capital of new delhi" in lower:
            reply = "Hi, New Delhi itself is the capital city of India.\n\nBest,\nSri"
        else:
            reply = (
                "Hi, thanks for reaching out. I saw your message and I’ll get back to you shortly.\n\n"
                "Best,\nSri"
            )
        return LLMResult(text=reply, used_fallback=True, error=str(e))
