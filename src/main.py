from pathlib import Path

import gradio as gr
from dotenv import load_dotenv

load_dotenv()  # load the API key from .env first

from data_processor import read_transcript, clean_text
from llm_processor import create_script
from tts_generator import tts_generator

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


def make_recap(file_path):
    if file_path is None:
        raise gr.Error("Please upload a transcript (.txt)")

    text = clean_text(read_transcript(file_path))
    script = create_script(text)

    audio_path = tts_generator(output_dir=OUTPUT_DIR).generate_audio(script)
    if audio_path is None:
        raise gr.Error("Audio generation failed. Check the terminal for details.")

    return script, str(audio_path)


demo = gr.Interface(
    fn=make_recap,
    inputs=gr.File(label="Upload class transcript (.txt)", type="filepath"),
    outputs=[
        gr.Textbox(label="Recap script"),
        gr.Audio(label="Recap podcast"),
    ],
    title="Lesson Recapper",
)

if __name__ == "__main__":
    demo.launch(share=True)
