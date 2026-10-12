# ========================================
# Podcast Studio - Text-to-Speech
# ========================================

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI


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
            print("Generating podcast audio...")

            with self.client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice="alloy",
                input=text
            ) as response:

                response.stream_to_file(audio_path)

            print("✓ Audio generated successfully!")
            print(f"✓ Saved to: {audio_path}")

            return audio_path

        except Exception as e:
            print(f"✗ TTS error: {e}")
            return None

