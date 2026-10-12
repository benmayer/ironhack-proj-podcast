"""
data_processor.py
Step 1 of the Podcast Studio pipeline: read the input file and clean the text.

main.py uses it like this:
    from data_processor import read_transcript, clean_text
    text = clean_text(read_transcript(file_path))

Supported inputs: .txt, .md, .srt, .vtt and .pdf
(.pdf needs the "pypdf" package -> add "pypdf" to requirements.txt)
"""

import re

# Filler words to remove. Only words that never carry meaning;
# "like" or "so" are NOT here, because they are often real words.
FILLER_WORDS = ["um", "umm", "uh", "uhh", "uhm", "erm", "er", "ah", "hmm", "mhm"]


def read_transcript(file_path):
    """Read a .txt / .md / .srt / .vtt / .pdf file and return its raw text."""
    if file_path is None:
        raise ValueError("No file was given.")

    file_path = str(file_path)

    if file_path.lower().endswith(".pdf"):
        from pypdf import PdfReader  # imported here, so .txt works without pypdf

        reader = PdfReader(file_path)
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages)
    else:
        # errors="ignore" skips strange bytes instead of crashing
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            text = f.read()

    if not text.strip():
        raise ValueError("The file is empty or no text could be read from it.")
    return text


def clean_text(text):
    """Remove timestamps, filler words, noise tags and extra spaces."""

    # 1. Subtitle files (.srt / .vtt): drop the header, the numbered lines
    #    and the "00:00:01,000 --> 00:00:04,000" timing lines
    text = re.sub(r"^WEBVTT.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^.*-->.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    # 2. Timestamps like 12:05, 1:02:33, [00:12:05], (12:05.300)
    text = re.sub(r"[\[\(]?\b\d{1,2}:\d{2}(:\d{2})?([.,]\d+)?\b[\]\)]?", "", text)

    # 3. Noise tags like [inaudible], [music], (laughter)
    text = re.sub(
        r"[\[\(](inaudible|music|laughter|laughs|applause|crosstalk|silence|noise)[\]\)]",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # 4. Filler words, including a comma right after them ("um, so" -> "so")
    fillers = "|".join(FILLER_WORDS)
    text = re.sub(rf"\b({fillers})\b[,.]?", "", text, flags=re.IGNORECASE)

    # 5. Words repeated by accident: "the the" -> "the"
    text = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", text, flags=re.IGNORECASE)

    # 6. Strange characters (emoji, control symbols); keep letters incl. accents
    text = re.sub(r"[^\w\s.,;:!?'\"()\-–—%€$&/]", " ", text)

    # 7. Tidy spaces and punctuation
    text = re.sub(r"\s+", " ", text)              # many spaces/newlines -> one space
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)  # "hello ," -> "hello,"
    text = re.sub(r"([,.])(\s*[,.])+", r"\1", text)  # ", ," or ". ," -> one sign
    text = re.sub(r"^[\s,.;:]+", "", text)        # no punctuation at the very start

    return text.strip()


# Test this file on its own:  python src/data_processor.py
if __name__ == "__main__":
    sample = """WEBVTT

1
00:00:01.000 --> 00:00:04.000
[00:00:01] Teacher: Um, good morning everyone. Today we we talk about Python.

2
00:00:05.000 --> 00:00:09.000
12:05 So, uh, a list is   an ordered collection. [inaudible]
Uhm, any questions?? 🙂
"""
    print("BEFORE:\n", sample)
    print("AFTER:\n", clean_text(sample))