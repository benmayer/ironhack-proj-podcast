"""LLM script generation: turns cleaned lesson text into a podcast script of a chosen length.

Contract (see main.py):
    create_script(text: str, minutes: int = 5, instructions: str = "") -> str

Input:  cleaned transcript text (timestamps / filler words already removed).
Output: plain spoken-word script, no markdown or stage directions, so it can be
        passed directly to the text-to-speech step.
"""

import json
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

# A model asked for thousands of words in one reply writes far less than requested.
# From this length on, the script is written section by section instead.
SECTIONED_FROM_MINUTES = 10

# How many characters of the script written so far each new section gets to see.
CONTEXT_CHARS = 1_200


def _key_points(minutes: int) -> int:
    eligible = [m for m in KEY_POINTS_BY_MINUTES if m <= minutes]
    return KEY_POINTS_BY_MINUTES[max(eligible)] if eligible else KEY_POINTS_BY_MINUTES[5]


def _format_duration(minutes: int) -> str:
    return "1 hour" if minutes == 60 else f"{minutes} minutes"


PERSONA = (
    "You are a friendly, encouraging teaching assistant who records recap podcasts "
    "for students after a lesson."
)


def build_system_prompt(minutes: int = 5, instructions: str = "") -> str:
    words = minutes * WORDS_PER_MINUTE
    prompt = f"""{PERSONA}

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

    return prompt + _listener_block(instructions)


def _listener_block(instructions: str) -> str:
    instructions = instructions.strip()[:MAX_INSTRUCTIONS_CHARS]
    if not instructions:
        return ""
    return f"""

The listener has added their own instructions. Adapt the script's focus, tone, and \
style to follow them. The formatting rules and the target length still apply, \
and you must still only use the lesson material.
Listener instructions: {instructions}"""


NOTES_PROMPT = """You are helping prepare a lesson recap. Read this section of a lesson \
transcript and list its key learning points as short bullet points (max {max_bullets}), including any \
important definitions, examples, or terms. Output only the bullet points."""


def _max_bullets(minutes: int) -> int:
    """Longer podcasts need more detail, so keep more notes per transcript chunk."""
    return 8 if minutes <= 10 else 15 if minutes <= 30 else 20


_client = None


def _get_client() -> OpenAI:
    """Create the OpenAI client lazily so importing this module never needs an API key."""
    global _client
    if _client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")
        _client = OpenAI()
    return _client


def _chat(system: str, user: str, temperature: float = 0.7, json_mode: bool = False) -> str:
    extra = {"response_format": {"type": "json_object"}} if json_mode else {}
    response = _get_client().chat.completions.create(
        model=MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **extra,
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


PLAN_PROMPT = """You are planning a recap podcast for students after a lesson. From the \
lesson material, choose the {n} most important learning points and put them in the order \
that makes the best teaching flow.

Respond with JSON only, in this shape:
{{"points": [{{"title": "short title", "details": "1-2 sentences on what to cover, using only facts from the material"}}]}}"""

SECTION_PROMPT = """You are writing one section of a longer recap podcast script.

The full podcast covers these points, in order:
{outline}

You are writing section {k} of {n}: "{title}".
What to cover: {details}

Length: about {words} words. Write at least that much by going into depth: explain \
the idea, give a concrete example or analogy from the material, and say why it matters.
{position}
Script so far (the end of it, for flow; do not repeat anything already said):
\"\"\"{previous}\"\"\"
"""


def _plan_points(material: str, n: int, instructions: str) -> list[dict]:
    """Ask the model for the n learning points to cover. Returns [] if the answer is unusable."""
    system = PLAN_PROMPT.format(n=n)
    if instructions.strip():
        system += (
            "\nThe listener asked for this, so let it shape which points you pick: "
            + instructions.strip()[:MAX_INSTRUCTIONS_CHARS]
        )
    try:
        data = json.loads(_chat(system, f"Lesson material:\n\n{material}", 0.3, json_mode=True))
        points = [
            {"title": str(p["title"]), "details": str(p.get("details", ""))}
            for p in data["points"]
            if isinstance(p, dict) and p.get("title")
        ]
    except (ValueError, KeyError, TypeError):
        return []
    return points[:n]


def _create_sectioned_script(material: str, minutes: int, instructions: str) -> str:
    """Write a long script one learning point at a time so each part hits its length."""
    points = _plan_points(material, _key_points(minutes), instructions)
    if not points:
        return ""  # caller falls back to a single request

    n = len(points)
    words_each = minutes * WORDS_PER_MINUTE // n
    outline = "\n".join(f"{i}. {p['title']}" for i, p in enumerate(points, start=1))
    system = (
        PERSONA
        + "\n\nFormatting rules (the script is read by a text-to-speech engine):\n"
        "- Output only the words to be spoken, as plain paragraphs.\n"
        "- No markdown, bullet points, headings, emojis, or stage directions like [music].\n"
        "- Only use information from the lesson material. Do not invent facts."
        + _listener_block(instructions)
    )

    script = ""
    for k, point in enumerate(points, start=1):
        if k == 1:
            position = (
                "This is the first section: open with a short, warm welcome and a preview "
                "of the topics from the list above, then move into this point."
            )
        elif k == n:
            position = (
                "This is the last section: after this point, close with a brief wrap-up "
                "and a motivating sign-off."
            )
        else:
            position = (
                "Start with a natural transition from the previous section. "
                "Do not welcome the listener or wrap up."
            )
        user = SECTION_PROMPT.format(
            outline=outline, k=k, n=n, title=point["title"], details=point["details"],
            words=words_each, position=position, previous=script[-CONTEXT_CHARS:] or "(nothing yet)",
        )
        user += f"\nLesson material:\n\n{material}"
        print(f"  writing section {k}/{n}: {point['title']}")
        script += _chat(system, user) + "\n\n"
    return script.strip()


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
        notes_prompt = NOTES_PROMPT.format(max_bullets=_max_bullets(minutes))
        if instructions.strip():
            notes_prompt += (
                "\nPay extra attention to anything relevant to this request from the listener: "
                + instructions.strip()[:MAX_INSTRUCTIONS_CHARS]
            )
        notes = [_chat(notes_prompt, chunk, temperature=0.2) for chunk in chunks]
        material = "\n\n".join(notes)

    script = ""
    if minutes >= SECTIONED_FROM_MINUTES:
        script = _create_sectioned_script(material, minutes, instructions)
    if not script:
        script = _chat(build_system_prompt(minutes, instructions), f"Lesson material:\n\n{material}")

    print(f"Script: {len(script.split())} words (target {minutes * WORDS_PER_MINUTE})")
    return script


if __name__ == "__main__":
    # Quick manual check: python llm_processor.py path/to/cleaned.txt
    import sys

    # Optional second argument: minutes, e.g. python llm_processor.py cleaned.txt 10
    minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    with open(sys.argv[1], encoding="utf-8") as f:
        print(create_script(f.read(), minutes))
