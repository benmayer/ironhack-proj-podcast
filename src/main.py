from pathlib import Path

import gradio as gr
from dotenv import load_dotenv

load_dotenv()  # load the API key from .env first

from data_processor import read_transcript, clean_text
from llm_processor import create_script
from tts_generator import tts_generator

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


DURATIONS = [
    ("5 minutes", 5),
    ("10 minutes", 10),
    ("15 minutes", 15),
    ("20 minutes", 20),
    ("30 minutes", 30),
    ("45 minutes", 45),
    ("1 hour", 60),
]


def make_recap(file_path, minutes, instructions):
    if file_path is None:
        raise gr.Error("Please upload a transcript (.txt)")

    text = clean_text(read_transcript(file_path))
    script = create_script(text, minutes=int(minutes), instructions=instructions or "")

    audio_path = tts_generator(output_dir=OUTPUT_DIR).generate_audio(script)
    if audio_path is None:
        raise gr.Error("Audio generation failed. Check the terminal for details.")

    return script, str(audio_path)


demo = gr.Interface(
    fn=make_recap,
    inputs=[
        gr.File(label="Upload class transcript (.txt)", type="filepath"),
        gr.Dropdown(
            choices=DURATIONS,
            value=5,
            label="Approximate podcast length",
            info="Longer podcasts cover more learning points.",
        ),
        gr.Textbox(
            label="Your instructions (optional)",
            placeholder="e.g. Focus on loops, explain it for a complete beginner, keep the tone playful",
            lines=3,
            max_lines=6,
        ),
    ],
    outputs=[
        gr.Textbox(label="Recap script"),
        gr.Audio(label="Recap podcast"),
    ],
    title="Lesson Recapper",
)

if __name__ == "__main__":
    demo.launch(share=True)
