// --- State Management ---
let appState = {
    cards: [],        // The initial 10
    badCard: null,    // The one LLM picked
    goodCards: [],    // The other 9
    stage: 1
};

// --- Model Selection ---
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

// Load models on page load
loadModels();

// --- Helpers ---
function escapeHTML(str) {
    return str.replace(/[&<>"']/g, function(m) {
        return {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[m];
    });
}

function setStage(stageNum) {
    appState.stage = stageNum;
    
    // Update View
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
    document.getElementById(`view-${stageNum}`).classList.add('active');

    // Update Indicators
    document.querySelectorAll('.step').forEach((el, idx) => {
        el.classList.remove('active', 'done');
        if (idx + 1 < stageNum) el.classList.add('done');
        if (idx + 1 === stageNum) el.classList.add('active');
    });

    // Update Progress Line
    const percentage = ((stageNum - 1) / 2) * 100;
    document.getElementById('progressFill').style.width = `${percentage}%`;

    hideMessage();
}

function goToStage(num) {
    setStage(num);
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showMessage(text, type = 'info') {
    const el = document.getElementById('messageArea');
    el.textContent = text;
    el.className = `feedback ${type}`;
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
        btn.innerHTML = `⏳ ${loadingText}`;
    } else {
        btn.disabled = false;
        btn.innerHTML = defaultText;
    }
}

function createCardHTML(card, index, isBad = false) {
    return `
        <div class="${isBad ? 'reason-header' : ''}" style="font-size: 0.8em; color: #888; margin-bottom:5px;">#${index + 1}</div>
        <div class="card-content card-front">${card.front}</div>
        <div class="card-content card-back">${escapeHTML(card.back).replace(/\n/g, '<br>')}</div>
    `;
}

function resetApp() {
    appState = { cards: [], badCard: null, goodCards: [], stage: 1 };
    document.getElementById('cards-container-1').innerHTML = '';
    document.getElementById('deckStats').textContent = 'Нажмите кнопку ниже, чтобы выбрать 10 случайных карточек.';
    const existingBtn = document.getElementById('btn-to-analysis');
    if (existingBtn) existingBtn.remove();
    goToStage(1);
}

// --- API Actions ---

async function selectCards() {
    setLoading('btn-select', true, '🎲 Выбрать', 'Загрузка...');
    
    try {
        const res = await fetch('/api/select_cards');
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.error);

        appState.cards = data.cards;
        document.getElementById('deckStats').textContent = `Найдено ${data.total_cards} карточек. Выбрана десятка для анализа.`;

        const container = document.getElementById('cards-container-1');
        container.innerHTML = '';
        
        data.cards.forEach((card, idx) => {
            const div = document.createElement('div');
            div.className = 'card';
            div.innerHTML = createCardHTML(card, idx);
            container.appendChild(div);
        });

        // Show "Next" button if hidden (logic flow)
        // But actually, we can just show a button at the bottom of the grid or in controls
        const controls = document.querySelector('#view-1 .controls');
        let nextBtn = document.getElementById('btn-to-analysis');
        if (!nextBtn) {
            nextBtn = document.createElement('button');
            nextBtn.className = 'btn btn-primary';
            nextBtn.innerText = '🔍 Анализ LLM';
            nextBtn.onclick = selectWorst;
            nextBtn.id = 'btn-to-analysis';
            controls.appendChild(nextBtn);
        }

    } catch (err) {
        showMessage(`Ошибка: ${err.message}`, 'error');
    } finally {
        setLoading('btn-select', false, '🎲 Обновить выбор', 'Загрузка...');
    }
}

async function selectWorst() {
    setLoading('btn-to-analysis', true, '🔍 Анализ LLM', 'LLM думает...');
    
    try {
        const res = await fetch('/api/select_worst', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cards: appState.cards })
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        appState.badCard = data.worst_card;
        appState.goodCards = data.good_cards;

        // Render Stage 2
        const badWrapper = document.getElementById('bad-card-wrapper');
        badWrapper.innerHTML = createCardHTML(data.worst_card, data.worst_index, true);
        
        if(data.llm_reason) {
            const reasonEl = document.getElementById('llm-reason');
            reasonEl.style.display = 'block';
            reasonEl.innerHTML = `<strong style="color: #92400e;">Почему это плохо:</strong><br>${data.llm_reason}`;
        }

        const goodContainer = document.getElementById('good-cards-grid');
        goodContainer.innerHTML = '';
        data.good_cards.forEach((card, idx) => {
            const div = document.createElement('div');
            div.className = 'card';
            div.innerHTML = createCardHTML(card, idx);
            goodContainer.appendChild(div);
        });

        goToStage(2);

    } catch (err) {
        showMessage(`Ошибка анализа: ${err.message}`, 'error');
    } finally {
        setLoading('btn-to-analysis', false, '🔍 Анализ LLM', 'LLM думает...');
    }
}

async function generateBack() {
    setLoading('btn-generate', true, '🤖 Сгенерировать ответ', 'Генерация...');
    
    // Pre-fill editor
    document.getElementById('editor-front').innerHTML = appState.badCard.front;
    document.getElementById('editor-back').value = '';
    document.getElementById('editor-back').disabled = true;

    goToStage(3);

    try {
        const res = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                front: appState.badCard.front,
                good_cards: appState.goodCards
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        document.getElementById('editor-back').value = data.new_back;
        document.getElementById('editor-back').disabled = false;
        document.getElementById('editor-back').focus();

    } catch (err) {
        document.getElementById('editor-back').value = 'Ошибка генерации: ' + err.message;
        document.getElementById('editor-back').style.borderColor = 'var(--danger)';
        document.getElementById('editor-back').disabled = false;
    } finally {
        setLoading('btn-generate', false, '🤖 Перегенерировать', 'Генерация...');
    }
}

async function saveCard() {
    const newBack = document.getElementById('editor-back').value;
    if (!newBack.trim()) {
        showMessage('Ответ не может быть пустым', 'error');
        return;
    }

    setLoading('btn-save', true, '✓ Сохранить', 'Запись в Anki...');

    try {
        const res = await fetch('/api/update_card', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_id: appState.badCard.id,
                new_back: newBack
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        showMessage('Карточка успешно обновлена!', 'success');
        
        setTimeout(() => {
            resetApp();
        }, 1500);

    } catch (err) {
        showMessage(`Ошибка сохранения: ${err.message}`, 'error');
    } finally {
        setLoading('btn-save', false, '✓ Сохранить', 'Запись в Anki...');
    }
}
