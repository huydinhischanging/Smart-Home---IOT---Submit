//src/dashboard/elderly_panel.js
export function renderElderlyPanel(device) {

    let unit = "";
    let statusClass = "";
    let statusText = "Bình thường";
    let statusColor = "var(--green)";
    let icon = device.icon || "📡";
    let accentColor = "var(--accent)";

    const val = parseFloat(device.value);

    if (isNaN(val)) {
        return `
            <div class="elderly-sensor-card" data-code="${device.code}">
                <div class="elderly-icon">${icon}</div>
                <div class="elderly-info">
                    <label>${device.name}</label>
                    <div class="elderly-value">--</div>
                    <div class="elderly-status-row">
                        <span class="elderly-status-dot" style="background:var(--text-dim)"></span>
                        <span class="elderly-status-txt" style="color:var(--text-dim)">Chờ dữ liệu</span>
                    </div>
                </div>
            </div>
        `;
    }

    switch (device.code) {

        case 'heart_rate':
            unit = "BPM";
            icon = device.icon || "❤️";
            accentColor = "#f87171";
            if (val < 50 || val > 120) {
                statusClass = "critical-pulse";
                statusText = "Cần chú ý!";
                statusColor = "#f87171";
            } else if (val >= 60 && val <= 100) {
                statusText = "Bình thường";
                statusColor = "var(--green)";
            } else {
                statusText = "Theo dõi";
                statusColor = "#fbbf24";
            }
            break;

        case 'room_temp':
            unit = "°C";
            icon = device.icon || "🌡️";
            accentColor = "#fb923c";
            if (val > 38) {
                statusClass = "critical-pulse";
                statusText = "Quá nóng!";
                statusColor = "#f87171";
            } else if (val >= 18 && val <= 28) {
                statusText = "Thoải mái";
                statusColor = "var(--green)";
            } else {
                statusText = "Chú ý";
                statusColor = "#fbbf24";
            }
            break;

        case 'humidity':
            unit = "%";
            icon = device.icon || "💧";
            accentColor = "#38bdf8";
            if (val >= 40 && val <= 70) {
                statusText = "Lý tưởng";
                statusColor = "var(--green)";
            } else {
                statusText = "Chú ý";
                statusColor = "#fbbf24";
            }
            break;

        case 'light_level':
            unit = "Lux";
            icon = device.icon || "💡";
            accentColor = "#fbbf24";
            if (val < 5) {
                statusClass = "critical-pulse";
                statusText = "Quá tối!";
                statusColor = "#f87171";
            } else if (val >= 100) {
                statusText = "Đủ sáng";
                statusColor = "var(--green)";
            } else {
                statusText = "Hơi tối";
                statusColor = "#fbbf24";
            }
            break;

        case 'spo2':
            unit = "%";
            icon = device.icon || "🫁";
            accentColor = "#60a5fa";
            if (val < 90) {
                statusClass = "critical-pulse";
                statusText = "Cần trợ giúp!";
                statusColor = "#f87171";
            } else if (val >= 95) {
                statusText = "Tốt";
                statusColor = "var(--green)";
            } else {
                statusText = "Theo dõi";
                statusColor = "#fbbf24";
            }
            break;

        default:
            unit = "";
    }

    const displayVal = Number.isInteger(val) ? val : val.toFixed(1);

    return `
        <div class="elderly-sensor-card ${statusClass}" data-code="${device.code}"
             style="--card-accent:${accentColor};">
            <div class="elderly-icon-wrap">
                <div class="elderly-icon">${icon}</div>
                <div class="elderly-icon-bg" style="background:${accentColor}20"></div>
            </div>
            <div class="elderly-info">
                <label>${device.name}</label>
                <div class="elderly-value" style="color:${accentColor}">
                    ${displayVal}<small>${unit}</small>
                </div>
                <div class="elderly-status-row">
                    <span class="elderly-status-dot" style="background:${statusColor};box-shadow:0 0 6px ${statusColor}50"></span>
                    <span class="elderly-status-txt" style="color:${statusColor}">${statusText}</span>
                </div>
            </div>
        </div>
    `;
}
