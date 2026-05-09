// --- State Management ---
let appState = {
    cards: [],
    badCard: null,
    goodCards: [],
    stage: 1
};

// --- Helpers ---
function setStage(stageNum) {
    appState.stage = stageNum;

    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
    document.getElementById(`view-${stageNum}`).classList.add('active');

    document.querySelectorAll('.step').forEach((el, idx) => {
        el.classList.remove('active', 'done');
        if (idx + 1 < stageNum) el.classList.add('done');
        if (idx + 1 === stageNum) el.classList.add('active');
    });

    const percentage = ((stageNum - 1) / 2) * 100;
    document.getElementById('progressFill').style.width = `${percentage}%`;

    hideMessage();
}

function goToStage(num) {
    setStage(num);
    window.scrollTo({ top: 0, behavior: 'smooth' });
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
