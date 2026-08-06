from flask import Flask, render_template, request, jsonify
import requests
import random
import re
import json
import os

app = Flask(__name__)

# Настройки
ANKI_URL = "http://localhost:8765"
LM_BASE_URL = "http://localhost:8080"
LM_URL = f"{LM_BASE_URL}/v1/chat/completions"
DECK = ''
EXAMPLE_COUNT = 10
CARDS_TO_SELECT = 10
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
DEFAULT_MODEL = ""


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"model": DEFAULT_MODEL, "deck": DECK}


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_model():
    settings = load_settings()
    return settings.get("model", DEFAULT_MODEL)

def anki(action, **params):
    try:
        r = requests.post(
            ANKI_URL,
            json={
                "action": action,
                "version": 6,
                "params": params
            },
            timeout=10
        ).json()
        if r.get("error"):
            raise Exception(r["error"])
        return r["result"]
    except Exception as e:
        raise Exception(f"Anki Error: {str(e)}")

def llm_request(payload, timeout=300):
    r = requests.post(LM_URL, json=payload, timeout=timeout).json()
    if r.get("error"):
        msg = r["error"].get("message", r["error"]) if isinstance(r["error"], dict) else r["error"]
        raise Exception(f"LLM error: {msg}")
    if "choices" not in r or not r["choices"]:
        raise Exception(f"LLM error: unexpected response: {r}")
    return r

def extract_json(text, required_keys=None):
    """Extract the first valid JSON object from arbitrary LLM text.

    If required_keys is given, the object matching those keys (if any)
    is preferred over earlier objects in the text.
    """
    if not text:
        return None

    def get_candidates():
        try:
            yield json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            try:
                yield json.loads(fenced.group(1))
            except (json.JSONDecodeError, TypeError):
                pass

        start = text.find("{")
        while start != -1:
            depth = 0
            in_string = False
            escaped = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_string:
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == '"':
                        in_string = False
                else:
                    if ch == '"':
                        in_string = True
                    elif ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            candidate = text[start:i + 1]
                            try:
                                yield json.loads(candidate)
                            except (json.JSONDecodeError, TypeError):
                                break
            start = text.find("{", start + 1)

    if not required_keys:
        required_keys = []

    fallback = None
    for obj in get_candidates():
        if not isinstance(obj, dict):
            continue
        if fallback is None:
            fallback = obj
        if all(key in obj for key in required_keys):
            return obj
    return fallback


def strip_html(text):
    text = text.replace("\n", "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(p|div|li|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()

def ask_llm_worst_card(cards_info):
    cards_text = "\n---\n".join(
        [f"**{i+1}. Front:** {c['front']}\n\n**Back:** {c['back'].replace(chr(10), ' ')}" for i, c in enumerate(cards_info)]
    )

    system_prompt = (
        "You are an expert at evaluating Anki flashcard quality for English learners. "
        "Pay special attention to irregular verbs: the front side shows the base verb, "
        "and a high-quality card must list the second (past simple) and third (past "
        "participle) forms on the back side. Cards missing this information on the "
        "back should be penalized."
    )
    
    prompt = f"""You are an expert at evaluating Anki flashcard quality.

Here are {CARDS_TO_SELECT} Anki cards from a deck:

{cards_text}

1. Analyze each card for clarity and relevance of the answer to the question.
 2. Select the ONE card that is the WORST quality (unclear, wrong, or confusing).
 3. Provide a reason why it is bad.

Format your response as a JSON object:
{{
  "worst_index": <number 1 to {CARDS_TO_SELECT}>,
  "reason": "<explanation>"
}}
"""
    
    r = llm_request(
        {
            "model": get_model(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "chat_template_kwargs": {"enable_thinking": False},
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "max_tokens": 256
        },
        timeout=300
    )
    
    content = r["choices"][0]["message"]["content"]
    parsed = extract_json(content, required_keys=["worst_index"])
    if isinstance(parsed, dict):
        return parsed
    if not content.strip():
        raise Exception("LLM вернула пустой ответ (thinking не отключён?)")
    return {"worst_index": 1, "reason": "LLM failed to format output, defaulting to 1"}

def ask_llm_generate(front, good_examples):
    example_text = "\n---\n".join(
        [f"**Front:** {f}\n\n**Back:** {b.replace(chr(10), ' ')}" for f, b in good_examples]
    )

    system_prompt = (
        "You are an English teacher helping to improve Anki cards for learning English. "
        "The front side contains a word, phrase, or question. If it is an irregular "
        "verb, the back side must include its second (past simple) and third (past "
        "participle) forms, along with the translation or explanation."
    )
    
    prompt = f"""
You are an English teacher helping to improve Anki cards.

Here are EXAMPLES of good, clear cards from the same deck:
{example_text}

Create a perfect "Back" answer for this new card:
Front: {front}

Rules:
1. Follow the style of the examples.
2. Be accurate.
3. Do not add markdown formatting like **bold** unless necessary.
4. Do not include links to images.
5. Return ONLY the text of the back side.
"""
    
    r = llm_request(
        {
            "model": get_model(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "chat_template_kwargs": {"enable_thinking": False},
            "temperature": 0.5,
            "max_tokens": 1024
        },
        timeout=300
    )
    
    content = r["choices"][0]["message"]["content"].strip()
    if not content:
        raise Exception("LLM вернула пустой ответ (thinking не отключён?)")
    return content

@app.route('/api/models', methods=['GET'])
def models_api():
    try:
        r = requests.get(f"{LM_BASE_URL}/v1/models", timeout=10).json()
        models = []
        for m in r.get("data", []):
            models.append(m.get("id", m.get("name", "unknown")))
        return jsonify({"models": models})
    except Exception as e:
        return jsonify({"error": str(e), "models": []}), 500

@app.route('/api/decks', methods=['GET'])
def decks_api():
    try:
        deck_names = anki("deckNames")
        return jsonify({"decks": deck_names})
    except Exception as e:
        return jsonify({"error": str(e), "decks": []}), 500


@app.route('/api/settings', methods=['GET', 'POST'])
def settings_api():
    if request.method == 'GET':
        settings = load_settings()
        return jsonify(settings)
    else:
        data = request.json
        settings = load_settings()
        if "model" in data:
            settings["model"] = data["model"]
        if "deck" in data:
            settings["deck"] = data["deck"]
        save_settings(settings)
        return jsonify({"success": True, "model": settings.get("model"), "deck": settings.get("deck")})

def ask_llm_story(cards):
    words_text = "\n".join(
        [f"{i+1}. {c['front']} — {strip_html(c['back'])}" for i, c in enumerate(cards)]
    )

    prompt = f"""You are a creative English teacher. Write a short, coherent story in English that naturally incorporates ALL of the following words and phrases:

{words_text}

Rules:
1. Use each word or phrase at least once, naturally in context.
2. When a word or phrase first appears, wrap it in **bold** (e.g., **word**).
3. The story should be engaging and make sense as a whole.
4. Keep the story length reasonable (2-4 paragraphs).
5. Do not add any markdown formatting other than bold (**).
6. Return ONLY the story text, no preamble or explanation."""

    r = llm_request(
        {
            "model": get_model(),
            "messages": [{"role": "user", "content": prompt}],
            "chat_template_kwargs": {"enable_thinking": False},
            "temperature": 0.7,
            "max_tokens": 1500
        },
        timeout=300
    )

    content = r["choices"][0]["message"]["content"].strip()
    if not content:
        raise Exception("LLM вернула пустой ответ (thinking не отключён?)")
    return content


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/story')
def story():
    return render_template('story.html')


@app.route('/api/story_cards', methods=['POST'])
def story_cards_api():
    try:
        settings = load_settings()
        selected_deck = settings.get("deck", DECK)

        card_ids = anki("findCards", query=f'deck:"{selected_deck}" is:learn')

        if len(card_ids) < 3:
            lapse_ids = anki("findCards", query=f'deck:"{selected_deck}" prop:lapses>=1')
            card_ids = list(set(card_ids + lapse_ids))

        if len(card_ids) == 0:
            return jsonify({"error": "Нет карточек для повторения в этой колоде"}), 400

        note_ids = anki("cardsToNotes", cards=card_ids)
        note_ids = list(set(note_ids))

        notes = anki("notesInfo", notes=note_ids)

        cards = []
        for note in notes:
            front_raw = note["fields"]["Front"]["value"]
            back_raw = note["fields"]["Back"]["value"]
            cards.append({
                "id": note["noteId"],
                "front": strip_html(front_raw),
                "back": strip_html(back_raw)
            })

        random.shuffle(cards)
        cards = cards[:CARDS_TO_SELECT]

        return jsonify({"cards": cards, "total": len(cards)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/story_generate', methods=['POST'])
def story_generate_api():
    try:
        data = request.json
        cards = data.get('cards')

        if not cards or len(cards) == 0:
            return jsonify({"error": "Нет карточек для рассказа"}), 400

        story = ask_llm_story(cards)

        return jsonify({"story": story})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/select_cards', methods=['GET'])
def select_cards_api():
    try:
        settings = load_settings()
        selected_deck = settings.get("deck", DECK)
        note_ids = anki("findNotes", query=f'deck:"{selected_deck}"')
        if len(note_ids) < CARDS_TO_SELECT:
            return jsonify({"error": f"В колоде недостаточно карточек ({len(note_ids)})"}), 400
        
        selected_ids = random.sample(note_ids, CARDS_TO_SELECT)
        selected_notes = anki("notesInfo", notes=selected_ids)
        
        cards = []
        for note in selected_notes:
            front_raw = note["fields"]["Front"]["value"]
            back_raw = note["fields"]["Back"]["value"]
            
            cards.append({
                "id": note["noteId"],
                "front": strip_html(front_raw),
                "back": back_raw
            })
        
        return jsonify({
            "cards": cards,
            "total_cards": len(note_ids)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/select_worst', methods=['POST'])
def select_worst_api():
    try:
        data = request.json
        cards = data.get('cards')
        
        if not cards:
            return jsonify({"error": "Нет карточек для анализа"}), 400
        
        cards_info = [{"front": c["front"], "back": c["back"]} for c in cards]
        llm_res = ask_llm_worst_card(cards_info)

        try:
            worst_idx = int(llm_res.get("worst_index", 1)) - 1
        except (ValueError, TypeError):
            worst_idx = 0
        reason = llm_res.get("reason", "Не указана причина")
        
        worst_idx = max(0, min(worst_idx, len(cards)-1))
        
        worst_card = cards[worst_idx]
        good_cards = [c for i, c in enumerate(cards) if i != worst_idx]
        
        return jsonify({
            "worst_card": worst_card,
            "good_cards": good_cards,
            "worst_index": worst_idx,
            "llm_reason": reason
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate_api():
    try:
        data = request.json
        front = data.get('front')
        good_cards = data.get('good_cards')
        
        examples = [(c["front"], c["back"]) for c in good_cards]
        new_back = ask_llm_generate(front, examples)
        
        return jsonify({"new_back": new_back})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update_card', methods=['POST'])
def update_card_api():
    try:
        data = request.json
        target_id = data.get('target_id')
        new_back = data.get('new_back')
        
        if not target_id or not new_back:
            return jsonify({"error": "Неполные данные"}), 400
        
        anki("updateNoteFields", note={
            "id": target_id,
            "fields": {"Back": new_back}
        })
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)