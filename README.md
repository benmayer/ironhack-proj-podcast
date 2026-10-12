# Podcast Studio / Lesson Recapper

A modular Python app that turns a raw class transcript or notes into a ~5 minute
recap podcast: a short script plus an audio (`.mp3`) version of it.

Each file has one job, so the team can work in parallel and test each step on its own.

## Pipeline

| Step | File | Job | Status |
|------|------|-----|--------|
| 1 | `src/data_processor.py` | Read the input file and clean the text | Done |
| 2 | `src/llm_processor.py` | Generate the podcast script with an LLM | Done |
| 3 | `src/tts_generator.py` | Convert the script to an `.mp3` in `outputs/` | Not started |
| 4 | `src/main.py` | Wire the steps together in a Gradio web app | Basic script only |

```
transcript file -> read_transcript() -> clean_text() -> create_script() -> generate_audio() -> .mp3
```

## Project structure

```
podcast-studio/
├── src/
│   ├── data_processor.py  # Read + clean input text
│   ├── llm_processor.py   # LLM prompting and script generation
│   ├── tts_generator.py   # Text-to-speech (.mp3)
│   └── main.py            # Entry point (Gradio app planned)
├── outputs/               # Generated audio files
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
- `create_script(text) -> str`: sends the cleaned text to the OpenAI API with a "friendly teaching assistant" system prompt and returns a plain spoken-word script (about 750 words, 5 key learning points, no markdown or stage directions, so it can go straight to text-to-speech).
- Transcripts longer than about 12,000 characters are split into chunks, each chunk is condensed into notes, and the script is generated from the combined notes.
- Raises `ValueError` on empty input and `RuntimeError` if `OPENAI_API_KEY` is missing.

Try it standalone: `python src/llm_processor.py path/to/cleaned.txt`

### `tts_generator.py`
Planned: `generate_audio(script) -> str` returning the path of the saved `.mp3` in `outputs/`.

### `main.py`
Currently runs the pipeline on a hardcoded `lesson.txt`. The plan is a Gradio app where users upload a transcript and get back the script and an audio player.

## Run

From the `src/` folder (once `tts_generator.py` is implemented):

```bash
python main.py
```

## Team notes / open decisions

- The script is returned as a single plain-text string. If the UI needs more (title, the 5 points as separate fields), `create_script` can return a dict instead.
- The script uses a single narrator. Two-host dialogue would need different voices in the TTS step.
- Never commit `.env`. It is listed in `.gitignore`.
