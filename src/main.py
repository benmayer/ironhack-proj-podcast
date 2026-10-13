from data_processor import read_transcript, clean_text
from llm_processor import create_script
from tts_generator import tts_generator
 
text   = clean_text(read_transcript("lesson.txt"))
script = create_script(text)

tts = tts_generator();

audio  = tts.generate_audio(script)
import gradio as gr
from dotenv import load_dotenv
load_dotenv() # load the API key from .env first
from data_processor import read_transcript, clean_text
from llm_processor import create_script
from tts_generator import generate_audio
def make_recap(file_path):
if file_path is None:
raise gr.Error("Please upload a transcript (.txt)")
text = clean_text(read_transcript(file_path))
script = create_script(text)
audio_path = generate_audio(script)
return script, audio_path
demo = gr.Interface(
fn=make_recap,
inputs=gr.File(label="Upload class transcript (.txt)",
type="filepath"),
outputs=[gr.Textbox(label="Recap script"),
gr.Audio(label="Recap podcast")],
title="Lesson Recapper",
)
demo.launch()
