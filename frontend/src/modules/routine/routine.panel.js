export function renderRoutinePanel(predictions) {
    // Giả sử predictions = [{time: '18:00', action: 'Living Light ON', probability: '92%'}]
    return `
        <div class="routine-box">
            <div class="diagnostic-header">🤖 ORACLE PREDICTIONS</div>
            <div class="routine-list">
                ${predictions.map(p => `
                    <div class="routine-item">
                        <span>🕒 ${p.time}</span>
                        <span class="routine-action">${p.action}</span>
                        <span class="routine-prob">${p.probability}</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}