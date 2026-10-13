"""LLM script generation: turns cleaned lesson text into a podcast script of a chosen length.

Contract (see main.py):
    create_script(text: str, minutes: int = 5, instructions: str = "") -> str

Input:  cleaned transcript text (timestamps / filler words already removed).
Output: plain spoken-word script, no markdown or stage directions, so it can be
        passed directly to the text-to-speech step.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ~150 spoken words per minute of audio.
WORDS_PER_MINUTE = 150

# Longer podcasts cover more learning points (minutes -> number of points).
# Durations not listed here fall back to the closest shorter entry.
KEY_POINTS_BY_MINUTES = {5: 5, 10: 7, 15: 9, 20: 10, 30: 12, 45: 15, 60: 18}

# Transcripts longer than this are split into chunks and summarised in two stages.
MAX_CHUNK_CHARS = 12_000

# Cap on user-supplied instructions, to keep the prompt small.
MAX_INSTRUCTIONS_CHARS = 1_000


def _key_points(minutes: int) -> int:
    eligible = [m for m in KEY_POINTS_BY_MINUTES if m <= minutes]
    return KEY_POINTS_BY_MINUTES[max(eligible)] if eligible else KEY_POINTS_BY_MINUTES[5]


def _format_duration(minutes: int) -> str:
    return "1 hour" if minutes == 60 else f"{minutes} minutes"


def build_system_prompt(minutes: int = 5, instructions: str = "") -> str:
    words = minutes * WORDS_PER_MINUTE
    prompt = f"""You are a friendly, encouraging teaching assistant who records recap \
podcasts for students after a lesson.

Turn the lesson material you are given into a podcast script that:
- covers the {_key_points(minutes)} most important learning points from the lesson
- lasts about {_format_duration(minutes)} when read aloud (roughly {words} words)
- opens with a short, warm welcome and a one-sentence preview of what is coming
- explains each point in simple, conversational language, with a quick example or analogy where it helps
- closes with a brief wrap-up and a motivating sign-off

Formatting rules (the script is read by a text-to-speech engine):
- Output only the words to be spoken, as plain paragraphs.
- No markdown, bullet points, headings, emojis, or stage directions like [music].
- Introduce each point in words ("First...", "Second...", etc.).
- Only use information from the lesson material. Do not invent facts."""

    instructions = instructions.strip()[:MAX_INSTRUCTIONS_CHARS]
    if instructions:
        prompt += f"""

The listener has added their own instructions. Adapt the script's focus, tone, and \
style to follow them. The formatting rules and the target length above still apply, \
and you must still only use the lesson material.
Listener instructions: {instructions}"""
    return prompt


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


def create_script(text: str, minutes: int = 5, instructions: str = "") -> str:
    """Generate a podcast script of about `minutes` minutes from lesson text.

    `instructions` is optional free text from the user (e.g. "focus on loops",
    "explain it like I'm a beginner") that the script adapts to.
    """
    if not text or not text.strip():
        raise ValueError("Cannot create a script from empty text.")

    chunks = chunk_text(text)

    if len(chunks) == 1:
        material = chunks[0]
    else:
        # Long transcript: condense each chunk into notes, then script from the combined notes.
        # The listener's instructions guide which details are worth keeping.
        notes_prompt = NOTES_PROMPT
        if instructions.strip():
            notes_prompt += (
                "\nPay extra attention to anything relevant to this request from the listener: "
                + instructions.strip()[:MAX_INSTRUCTIONS_CHARS]
            )
        notes = [_chat(notes_prompt, chunk, temperature=0.2) for chunk in chunks]
        material = "\n\n".join(notes)

    return _chat(build_system_prompt(minutes, instructions), f"Lesson material:\n\n{material}")


if __name__ == "__main__":
    # Quick manual check: python llm_processor.py path/to/cleaned.txt
    import sys

    # Optional second argument: minutes, e.g. python llm_processor.py cleaned.txt 10
    minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    with open(sys.argv[1], encoding="utf-8") as f:
        print(create_script(f.read(), minutes))
