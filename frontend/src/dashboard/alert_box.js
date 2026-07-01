// src/dashboard/alert_box.js
export function renderAlertItem(alert) {
    const time = alert.created_at
        ? new Date(alert.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
        : '--:--';
    const date = alert.created_at
        ? new Date(alert.created_at).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })
        : '';

    const readClass = alert.is_read ? ' is-read' : '';
    const idAttr = alert.id ? ` data-id="${alert.id}"` : '';
    const action = alert.suggested_action || {};
    const canConfirm = Boolean(alert.requires_confirmation && action.device_code);

    const levelIcons = {
        critical: '🔴',
        warning:  '🟡',
        info:     '🔵',
        ok:       '🟢',
    };
    const levelIcon = levelIcons[alert.level?.toLowerCase()] || '⚪';

    const ackBtn = alert.is_read ? '' : `
        <button class="alert-action-btn alert-ack-btn" title="Xác nhận đã đọc" data-action="ack">
            ✓ Đã xem
        </button>`;

    const confirmBtn = canConfirm ? `
        <button class="alert-action-btn alert-confirm-btn" title="Xác nhận hành động"
                data-action="confirm"
                data-device-code="${action.device_code}"
                data-value="${action.value || 'ON'}">
            ⚡ Bật ngay
        </button>` : '';

    const snoozeBtn = canConfirm ? `
        <button class="alert-action-btn alert-snooze-btn" title="Tắt gợi ý 1 giờ" data-action="mute-1h">
            🔕 Tắt 1h
        </button>` : '';

    const deleteBtn = `
        <button class="alert-delete-btn" title="Xóa" data-action="delete">✕</button>`;

    return `
        <div class="alert-item ${alert.level?.toLowerCase() || 'info'}${readClass}"${idAttr}>
            <div class="alert-item-icon">${levelIcon}</div>
            <div class="alert-item-body">
                <div class="alert-item-header">
                    <span class="alert-time">${date} ${time}</span>
                    ${!alert.is_read ? '<span class="alert-unread-dot"></span>' : ''}
                </div>
                <div class="alert-msg">${alert.message}</div>
                ${(confirmBtn || snoozeBtn || ackBtn) ? `
                <div class="alert-item-actions">
                    ${confirmBtn}${snoozeBtn}${ackBtn}
                </div>` : ''}
            </div>
            ${deleteBtn}
        </div>
    `;
}
