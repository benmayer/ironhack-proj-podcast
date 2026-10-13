# ========================================
# Podcast Studio - Text-to-Speech
# ========================================

import os
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI


# OpenAI's speech endpoint rejects input longer than 4096 characters,
# so longer scripts are sent in pieces (kept a bit under the limit).
MAX_TTS_CHARS = 4000


def split_text(text, max_chars=MAX_TTS_CHARS):
    """Split text into pieces of at most max_chars, breaking at sentence ends."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    pieces, current = [], ""
    for sentence in sentences:
        # A "sentence" that is itself too long: cut it at a space.
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


class tts_generator:
    """
    Converts a podcast script from text into an MP3 audio file.
    """

    def __init__(self, output_dir="output"):

        # Load environment variables from .env
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY was not found in .env"
            )

        # Connect to OpenAI
        self.client = OpenAI(api_key=api_key)

        # Create output directory if it does not exist
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        print("✓ Text-to-Speech initialized")


    def generate_audio(
        self,
        text,
        output_file="podcast.mp3"
    ):
        """
        Convert text into speech and save it as an MP3.

        Args:
            text: Podcast script to convert to speech.
            output_file: Name of the generated audio file.

        Returns:
            Path to the generated audio file,
            or None if generation fails.
        """

        # Check that text was provided
        if not text or not text.strip():
            print("✗ No text was provided.")
            return None

        audio_path = self.output_dir / output_file

        try:
            pieces = split_text(text)
            print(f"Generating podcast audio ({len(pieces)} part(s))...")

            # Each part becomes its own MP3 chunk; MP3 frames can simply be
            # appended one after another, so no audio tools are needed.
            with open(audio_path, "wb") as out:
                for i, piece in enumerate(pieces, start=1):
                    print(f"  part {i}/{len(pieces)}")
                    response = self.client.audio.speech.create(
                        model="tts-1",
                        voice="alloy",
                        input=piece
                    )
                    out.write(response.content)

            print("✓ Audio generated successfully!")
            print(f"✓ Saved to: {audio_path}")

            return audio_path

        except Exception as e:
            print(f"✗ TTS error: {e}")
            return None

