from data_processor import read_transcript, clean_text
from llm_processor import create_script
from tts_generator import generate_audio
 
text   = clean_text(read_transcript("lesson.txt"))
script = create_script(text)
audio  = generate_audio(script)
