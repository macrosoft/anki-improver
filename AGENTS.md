# AGENTS.md

## Setup

- Install dependencies: `pip install flask requests` (no `requirements.txt` exists)
- Start Anki with [Anki Connector](https://github.com/FooSoft/anki-connect) addon on port `8765`
- Start an OpenAI-compatible LLM server on `http://localhost:8080` (Ollama, llama.cpp, etc.)
- Run the app: `python app.py` → serves on `http://localhost:5000`

## Architecture

- **Entry point:** `app.py` (Flask, ~260 lines, all routes + logic)
- **Frontend:** `templates/index.html` (single file, all HTML + CSS + JS embedded, ~790 lines)
- **Settings:** `settings.json` (stores selected LLM model, gitignored)
- **No tests, no linter, no typechecker** configured

## Key Config in `app.py`

| Variable | Value | Note |
|---|---|---|
| `DECK` | `[Основная колода]` | Hardcoded Anki deck name |
| `ANKI_URL` | `http://localhost:8765` | Anki Connector endpoint |
| `LM_BASE_URL` | `http://localhost:8080` | LLM server base URL |
| `CARDS_TO_SELECT` | `10` | Cards per analysis round |

## Workflow

The 3-step flow: `/api/select_cards` → `/api/select_worst` → `/api/generate` → `/api/update_card`. Each step is sequential; the frontend manages state via JS. Adjusting `DECK` or port constants in `app.py` is the main way to reconfigure.

## UI Language

All UI labels are in Russian (`lang="ru"`). Keep that convention unless the user asks otherwise.
