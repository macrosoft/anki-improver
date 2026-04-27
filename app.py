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
DECK = '[Основная колода]'
EXAMPLE_COUNT = 10
CARDS_TO_SELECT = 10
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
DEFAULT_MODEL = "Qwen3.6-27B"


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"model": DEFAULT_MODEL}


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
    
    r = requests.post(
        LM_URL,
        json={
            "model": get_model(),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        },
        timeout=60
    ).json()
    
    content = r["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except:
        match = re.search(r'({.*})', content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return {"worst_index": 1, "reason": "LLM failed to format output, defaulting to 1"}

def ask_llm_generate(front, good_examples):
    example_text = "\n---\n".join(
        [f"**Front:** {f}\n\n**Back:** {b.replace(chr(10), ' ')}" for f, b in good_examples]
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
    
    r = requests.post(
        LM_URL,
        json={
            "model": get_model(),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5
        },
        timeout=60
    ).json()
    
    return r["choices"][0]["message"]["content"].strip()

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

@app.route('/api/settings', methods=['GET', 'POST'])
def settings_api():
    if request.method == 'GET':
        settings = load_settings()
        return jsonify(settings)
    else:
        data = request.json
        model = data.get("model")
        if not model:
            return jsonify({"error": "Модель не указана"}), 400
        settings = load_settings()
        settings["model"] = model
        save_settings(settings)
        return jsonify({"success": True, "model": model})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/select_cards', methods=['GET'])
def select_cards_api():
    try:
        note_ids = anki("findNotes", query=f'deck:"{DECK}"')
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
                "back": strip_html(back_raw)
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
        
        worst_idx = llm_res.get("worst_index", 1) - 1
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