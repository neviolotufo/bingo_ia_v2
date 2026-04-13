const drawInput = document.getElementById("drawInput");
const sendDrawBtn = document.getElementById("sendDrawBtn");
const voiceBtn = document.getElementById("voiceBtn");
const statusBox = document.getElementById("statusBox");
const drawnNumbersDiv = document.getElementById("drawnNumbers");
const cardsContainer = document.getElementById("cardsContainer");
const patternLabel = document.getElementById("patternLabel");
const winnerPanel = document.getElementById("winnerPanel");

let isSubmitting = false;
let isListening = false;
let recognition = null;

function speak(text) {
    if ("speechSynthesis" in window) {
        const msg = new SpeechSynthesisUtterance(text);
        msg.lang = "pt-BR";
        window.speechSynthesis.speak(msg);
    }
}

function updateDrawnNumbers(numbers) {
    drawnNumbersDiv.innerHTML = "";
    numbers.forEach(n => {
        const span = document.createElement("span");
        span.className = "badge text-bg-dark me-1 mb-1";
        span.textContent = n;
        drawnNumbersDiv.appendChild(span);
    });
}

function renderWinners(winners) {
    if (!winners || winners.length === 0) {
        winnerPanel.innerHTML = "";
        return;
    }

    const items = winners.map(w => {
        if (w.player) {
            return `<li><strong>${w.name}</strong> — Jogador: ${w.player}</li>`;
        }
        return `<li><strong>${w.name}</strong></li>`;
    }).join("");

    winnerPanel.innerHTML = `
        <div class="alert alert-warning shadow-sm rounded-4">
            <div class="fw-bold mb-2">BINGO detectado</div>
            <ul class="mb-0 ps-3">${items}</ul>
        </div>
    `;
}

function renderCards(cards) {
    cardsContainer.innerHTML = "";

    cards.forEach(card => {
        let tableRows = "";

        for (let r = 0; r < 5; r++) {
            let row = "<tr>";
            for (let c = 0; c < 5; c++) {
                if (r === 2 && c === 2) {
                    row += `<td class="marked free-cell">★</td>`;
                } else {
                    const markedClass = card.marks[r][c] ? "marked" : "";
                    row += `<td class="${markedClass}">${card.numbers[r][c]}</td>`;
                }
            }
            row += "</tr>";
            tableRows += row;
        }

        const badgeClass = card.is_winner ? "text-bg-success" : "text-bg-secondary";
        const badgeText = card.is_winner ? "BINGO" : "Em jogo";
        const winnerClass = card.is_winner ? "winner" : "";
        const playerLine = card.player ? `<div class="small text-muted">Jogador: ${card.player}</div>` : "";

        const html = `
            <div class="col-md-6 col-xl-4">
                <div class="card shadow-sm border-0 rounded-4 bingo-card ${winnerClass}" data-card-id="${card.id}">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2 gap-2">
                            <div>
                                <strong>${card.name}</strong>
                                ${playerLine}
                            </div>
                            <span class="badge ${badgeClass} winner-badge">${badgeText}</span>
                        </div>
                        <table class="table table-bordered text-center bingo-table mb-0">
                            <tbody>${tableRows}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
        cardsContainer.insertAdjacentHTML("beforeend", html);
    });
}

async function sendNumber(value) {
    if (isSubmitting) return;
    isSubmitting = true;

    sendDrawBtn.disabled = true;
    voiceBtn.disabled = true;

    try {
        const formData = new FormData();
        formData.append("value", value);

        const resp = await fetch(window.initialState.drawUrl, {
            method: "POST",
            body: formData
        });

        const data = await resp.json();

        if (!resp.ok || !data.ok) {
            statusBox.className = "alert alert-danger mb-0";
            statusBox.textContent = data.message || "Erro ao enviar número.";
            speak(data.message || "Erro");
            return;
        }

        statusBox.className = "alert alert-success mb-0";
        statusBox.textContent = `Número ${data.number} registrado com sucesso.`;

        patternLabel.textContent = data.pattern.toUpperCase();
        updateDrawnNumbers(data.drawn_numbers);
        renderCards(data.cards);
        renderWinners(data.winners);

        speak(`Saiu o número ${data.number}`);

        if (data.winners && data.winners.length > 0) {
            const names = data.winners
                .map(w => w.player ? `${w.name} do jogador ${w.player}` : w.name)
                .join(", ");

            statusBox.className = "alert alert-warning mb-0";
            statusBox.textContent = `BINGO! Cartela vencedora: ${names}`;
            speak(`Bingo! A cartela vencedora é ${names}`);
        }

        drawInput.value = "";
        drawInput.focus();
    } finally {
        isSubmitting = false;
        sendDrawBtn.disabled = false;
        voiceBtn.disabled = false;
    }
}

sendDrawBtn?.addEventListener("click", () => {
    const value = drawInput.value.trim();
    if (!value) return;
    sendNumber(value);
});

drawInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        sendDrawBtn.click();
    }
});

voiceBtn?.addEventListener("click", () => {
    if (isListening || isSubmitting) return;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        statusBox.className = "alert alert-danger mb-0";
        statusBox.textContent = "Seu navegador não suporta reconhecimento de voz.";
        return;
    }

    if (recognition) {
        try {
            recognition.abort();
        } catch (_) {}
    }

    recognition = new SpeechRecognition();
    recognition.lang = "pt-BR";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    isListening = true;
    voiceBtn.disabled = true;
    sendDrawBtn.disabled = true;

    statusBox.className = "alert alert-info mb-0";
    statusBox.textContent = "Ouvindo... fale o número sorteado.";

    recognition.onresult = function(event) {
        let transcript = "";

        for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                transcript += " " + event.results[i][0].transcript;
            }
        }

        transcript = transcript.trim();

        if (!transcript) {
            statusBox.className = "alert alert-danger mb-0";
            statusBox.textContent = "Não foi possível entender o número falado.";
            return;
        }

        drawInput.value = transcript;
        statusBox.className = "alert alert-secondary mb-0";
        statusBox.textContent = `Reconhecido: ${transcript}`;

        try {
            recognition.stop();
        } catch (_) {}

        isListening = false;
        voiceBtn.disabled = false;
        sendDrawBtn.disabled = false;

        sendNumber(transcript);
    };

    recognition.onerror = function() {
        isListening = false;
        voiceBtn.disabled = false;
        sendDrawBtn.disabled = false;

        statusBox.className = "alert alert-danger mb-0";
        statusBox.textContent = "Erro ao capturar áudio.";
    };

    recognition.onend = function() {
        isListening = false;
        voiceBtn.disabled = false;
        sendDrawBtn.disabled = false;
    };

    recognition.start();
});