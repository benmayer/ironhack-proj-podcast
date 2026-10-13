from data_processor import read_transcript, clean_text
from llm_processor import create_script
from tts_generator import tts_generator
 
text   = clean_text(read_transcript("lesson.txt"))
script = create_script(text)

tts = tts_generator();

audio  = tts.generate_audio(script)
