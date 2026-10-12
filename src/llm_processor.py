"""LLM script generation: turns cleaned lesson text into a ~5 minute podcast script.

Contract (see main.py):
    create_script(text: str) -> str

Input:  cleaned transcript text (timestamps / filler words already removed).
Output: plain spoken-word script, no markdown or stage directions, so it can be
        passed directly to the text-to-speech step.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ~150 spoken words per minute -> 5 minutes is roughly 750 words.
TARGET_WORDS = 750

# Transcripts longer than this are split into chunks and summarised in two stages.
MAX_CHUNK_CHARS = 12_000

SYSTEM_PROMPT = f"""You are a friendly, encouraging teaching assistant who records short \
recap podcasts for students after a lesson.

Turn the lesson material you are given into a podcast script that:
- covers exactly the 5 most important learning points from the lesson
- lasts about 5 minutes when read aloud (roughly {TARGET_WORDS} words)
- opens with a short, warm welcome and a one-sentence preview of what is coming
- explains each point in simple, conversational language, with a quick example or analogy where it helps
- closes with a brief wrap-up and a motivating sign-off

Formatting rules (the script is read by a text-to-speech engine):
- Output only the words to be spoken, as plain paragraphs.
- No markdown, bullet points, headings, emojis, or stage directions like [music].
- Introduce each point in words ("First...", "Second...", etc.).
- Only use information from the lesson material. Do not invent facts."""

NOTES_PROMPT = """You are helping prepare a lesson recap. Read this section of a lesson \
transcript and list its key learning points as short bullet points (max 8), including any \
important definitions, examples, or terms. Output only the bullet points."""

_client = None


def _get_client() -> OpenAI:
    """Create the OpenAI client lazily so importing this module never needs an API key."""
    global _client
    if _client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")
        _client = OpenAI()
    return _client


def _chat(system: str, user: str, temperature: float = 0.7) -> str:
    response = _get_client().chat.completions.create(
        model=MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks of at most max_chars, preferring paragraph, then sentence, breaks."""
    chunks, current = [], ""
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        # A single paragraph longer than the limit: fall back to sentence/word splitting.
        pieces = [paragraph] if len(paragraph) <= max_chars else _split_long(paragraph, max_chars)
        for piece in pieces:
            if current and len(current) + len(piece) + 1 > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    pieces, current = [], ""
    for sentence in paragraph.replace("? ", "?|").replace("! ", "!|").replace(". ", ".|").split("|"):
        # Guard against a "sentence" that is itself too long (e.g. no punctuation).
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:cut])
            sentence = sentence[cut:].lstrip()
        if current and len(current) + len(sentence) + 1 > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current:
        pieces.append(current)
    return pieces


def create_script(text: str) -> str:
    """Generate a ~5 minute podcast script with 5 key learning points from lesson text."""
    if not text or not text.strip():
        raise ValueError("Cannot create a script from empty text.")

    chunks = chunk_text(text)

    if len(chunks) == 1:
        material = chunks[0]
    else:
        # Long transcript: condense each chunk into notes, then script from the combined notes.
        notes = [_chat(NOTES_PROMPT, chunk, temperature=0.2) for chunk in chunks]
        material = "\n\n".join(notes)

    return _chat(SYSTEM_PROMPT, f"Lesson material:\n\n{material}")


if __name__ == "__main__":
    # Quick manual check: python llm_processor.py path/to/cleaned.txt
    import sys

    with open(sys.argv[1], encoding="utf-8") as f:
        print(create_script(f.read()))
