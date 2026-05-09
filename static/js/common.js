// --- Shared helpers ---
function escapeHTML(str) {
    return str.replace(/[&<>"']/g, function(m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
}

function showMessage(text, type) {
    const el = document.getElementById('messageArea');
    el.textContent = text;
    el.className = 'feedback ' + type;
}

function hideMessage() {
    const el = document.getElementById('messageArea');
    el.style.display = 'none';
    el.className = 'feedback';
}

function setLoading(btnId, isLoading, defaultText, loadingText) {
    const btn = document.getElementById(btnId);
    if (isLoading) {
        btn.disabled = true;
        btn.innerHTML = '⏳ ' + loadingText;
    } else {
        btn.disabled = false;
        btn.innerHTML = defaultText;
    }
}

// --- Model / Deck loading ---
async function loadModels() {
    const select = document.getElementById('modelSelect');
    try {
        const [modelsRes, settingsRes] = await Promise.all([
            fetch('/api/models'),
            fetch('/api/settings')
        ]);

        const modelsData = await modelsRes.json();
        const settingsData = await settingsRes.json();

        select.innerHTML = '';

        const models = modelsData.models || [];
        if (models.length === 0) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = '(нет моделей)';
            select.appendChild(opt);
            return;
        }

        const currentModel = settingsData.model || '';

        models.forEach(model => {
            const opt = document.createElement('option');
            opt.value = model;
            opt.textContent = model;
            if (model === currentModel) opt.selected = true;
            select.appendChild(opt);
        });

        if (!currentModel || !models.includes(currentModel)) {
            select.value = models[0];
        }

        loadDecks(settingsData);
    } catch (err) {
        select.innerHTML = '<option value="">(ошибка загрузки)</option>';
    }
}

async function selectModel(model) {
    if (!model) return;
    const deckSelect = document.getElementById('deckSelect');
    const deck = deckSelect && deckSelect.value ? deckSelect.value : undefined;
    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model, deck })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);
    } catch (err) {
        console.error('Failed to save model setting:', err);
    }
}

async function selectDeck(deck) {
    if (!deck) return;
    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ deck })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);
    } catch (err) {
        console.error('Failed to save deck setting:', err);
    }
}

async function loadDecks(settings) {
    const select = document.getElementById('deckSelect');
    try {
        const res = await fetch('/api/decks');
        const data = await res.json();

        select.innerHTML = '';

        const decks = data.decks || [];
        if (decks.length === 0) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = '(нет колод)';
            select.appendChild(opt);
            return;
        }

        const currentDeck = settings.deck || '';

        decks.forEach(deck => {
            const opt = document.createElement('option');
            opt.value = deck;
            opt.textContent = deck;
            if (deck === currentDeck) opt.selected = true;
            select.appendChild(opt);
        });

        if (!currentDeck || !decks.includes(currentDeck)) {
            select.value = decks[0];
        }
    } catch (err) {
        select.innerHTML = '<option value="">(ошибка загрузки)</option>';
    }
}

document.addEventListener('DOMContentLoaded', loadModels);
