# Podcast Studio / Lesson Recapper

A modular Python app that turns a raw class transcript or notes into a recap
podcast: a script plus an audio (`.mp3`) version of it. You choose the length
(5 minutes to 1 hour) and can add your own instructions to shape the script.

Each file has one job, so the team can work in parallel and test each step on its own.

## Pipeline

| Step | File | Job | Status |
|------|------|-----|--------|
| 1 | `src/data_processor.py` | Read the input file and clean the text | Done |
| 2 | `src/llm_processor.py` | Generate the podcast script with an LLM | Done |
| 3 | `src/tts_generator.py` | Convert the script to an `.mp3` in `outputs/` | Done |
| 4 | `src/main.py` | Wire the steps together in a Gradio web app | Done |

```
transcript file -> read_transcript() -> clean_text() -> create_script(minutes, instructions) -> generate_audio() -> .mp3
```

## Project structure

```
podcast-studio/
├── src/
│   ├── data_processor.py  # Read + clean input text
│   ├── llm_processor.py   # LLM prompting and script generation
│   ├── tts_generator.py   # Text-to-speech (.mp3)
│   └── main.py            # Gradio app wiring everything together
├── outputs/               # Generated audio files (ignored by git)
├── requirements.txt       # Dependencies
├── README.md
└── .env                   # API keys (local only, never committed)
```

## Setup

1. Clone the repo and create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   `pypdf` is only needed for PDF input.
3. Create a `.env` file in the project root:
   ```
   OPENAI_API_KEY=your-key-here
   # optional, defaults to gpt-4o-mini
   OPENAI_MODEL=gpt-4o-mini
   ```

## Modules

### `data_processor.py`
- `read_transcript(file_path) -> str`: reads `.txt`, `.md`, `.srt`, `.vtt` and `.pdf` files. Raises `ValueError` if the file is missing or empty.
- `clean_text(text) -> str`: removes subtitle headers and timings, timestamps, noise tags like `[inaudible]`, filler words (`um`, `uh`, ...) and accidental repeated words, then tidies whitespace. The result is a single line of plain text.

Try it standalone: `python src/data_processor.py`

### `llm_processor.py`
- `create_script(text, minutes=5, instructions="") -> str`: returns a plain spoken-word script (no markdown or stage directions, so it can go straight to text-to-speech) of about `minutes` minutes, at roughly 150 words per minute.
  - `minutes`: target length. The UI offers 5, 10, 15, 20, 30, 45 and 60. Longer podcasts cover more learning points (5 min: 5 points, 20 min: 10, 1 hour: 18).
  - `instructions`: optional free text from the user, such as "focus on loops" or "explain it for a beginner". The script adapts its focus, tone and style. The formatting rules and "only use the lesson material" still apply.
- **Short podcasts (5 min):** one request with a "friendly teaching assistant" system prompt.
- **Longer podcasts (10 min and up):** a model asked for thousands of words in one reply writes far less than requested, so the script is built in sections. One call plans the learning points, then each point is written as its own section (about `minutes x 150 / points` words), with a welcome in the first section and a wrap-up in the last. If planning fails, it falls back to a single request.
- **Long transcripts:** text over about 12,000 characters is split into chunks, and each chunk is condensed into notes first. Longer podcasts keep more notes per chunk (8, 15 or 20) so there is enough detail.
- The terminal prints the progress and the final word count against the target.
- Raises `ValueError` on empty input and `RuntimeError` if `OPENAI_API_KEY` is missing.

Try it standalone: `python src/llm_processor.py path/to/cleaned.txt 10` (the second argument is the length in minutes).

### `tts_generator.py`
- `tts_generator(output_dir="output")` is a class. `generate_audio(text, output_file="podcast.mp3")` converts text to speech with OpenAI `tts-1` and returns the path of the saved file, or `None` if it fails.
- OpenAI limits each speech request to 4,096 characters, so the script is split at sentence ends into parts of at most 4,000 characters. The audio for each part is appended into one `.mp3`.
- `main.py` passes `outputs/` as the output folder.

### `main.py`
A Gradio app with:
- a transcript upload,
- a length dropdown (5 minutes to 1 hour),
- an optional "Your instructions" box,
- outputs: the recap script as text and an audio player.

Longer podcasts take several minutes: a 20-minute one makes about 12 script requests plus a few audio requests. There is no progress bar yet, but the terminal shows progress.

## Run

```bash
python src/main.py
```

Then open the local URL printed in the terminal. The app currently launches with `share=True`, which also creates a temporary public link. Anyone with it can use the app on your OpenAI credits, so turn it off if you don't need it.

Each run calls the OpenAI API again (script and audio). Nothing is cached, so regenerating the same file with a different length costs tokens again.

## Team notes / open decisions

- The script is returned as a single plain-text string. If the UI needs more (title, the learning points as separate fields), `create_script` can return a dict instead.
- The script uses a single narrator. Two-host dialogue would need different voices in the TTS step.
- Never commit `.env`. It is listed in `.gitignore`.

## Presentation 
Our presentation can be found here: 
https://docs.google.com/presentation/d/1J2VMR2fDF-DEWNAG9MfrvaDgOxRMwgVxpmk9kCvmXf0/edit?slide=id.h1bb2586a8d7c1a83_0_10#slide=id.h1bb2586a8d7c1a83_0_10
