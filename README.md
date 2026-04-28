# Anki Improver

Web app that uses a local LLM to find and improve low-quality flashcards in your Anki decks.

## How It Works

A 3-step workflow:

1. **Select** — randomly picks 10 cards from your Anki deck
2. **Analyze** — AI evaluates them and identifies the weakest card with a reason
3. **Edit** — AI generates a better answer using the good cards as examples; you review and confirm before syncing back to Anki

## Prerequisites

- Python 3
- Anki running with the [Anki Connector](https://github.com/FooSoft/anki-connect) addon (default port `8765`)
- Anki running with at least one deck
- An OpenAI-compatible LLM server running on `http://localhost:8080` (e.g., Ollama, llama.cpp, LocalAI)

## Installation

1. Install dependencies:

```bash
pip install flask requests
```

2. Run the app:

```bash
python app.py
```

3. Open `http://localhost:5000` in your browser.

## Configuration

The selected LLM model is saved in `settings.json` (auto-created on first run). The default model is `Qwen3.6-27B`. Change the `DEFAULT_MODEL` in `app.py` if needed.

### Key Settings in `app.py`

| Variable | Default | Description |
|---|---|---|
| `ANKI_URL` | `http://localhost:8765` | Anki Connector address |
| `LM_BASE_URL` | `http://localhost:8080` | LLM server address |
| `DECK` | `[Основная колода]` | Fallback deck name (selected in UI) |
| `CARDS_TO_SELECT` | `10` | Number of cards per round |
| `DEFAULT_MODEL` | `Qwen3.6-27B` | Default LLM model |

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Main UI |
| `/api/models` | GET | List available LLM models |
| `/api/decks` | GET | List available Anki decks |
| `/api/settings` | GET / POST | Get or save settings |
| `/api/select_cards` | GET | Select random cards from Anki |
| `/api/select_worst` | POST | AI evaluates cards, finds the worst |
| `/api/generate` | POST | Generate improved answer |
| `/api/update_card` | POST | Save changes back to Anki |

## Tech Stack

- **Backend:** Python, Flask
- **Frontend:** Vanilla HTML, CSS, JavaScript
- **Anki Integration:** Anki Connector (JSON-RPC)
- **LLM:** Any OpenAI-compatible API server
