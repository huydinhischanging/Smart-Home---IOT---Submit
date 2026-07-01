// src/modules/alert/alert.controller.js
// This controller belongs to the SPA/Vite frontend path (src/main.js).
// It is not the Tactical AlertsCenter in frontend/index.html.
// Keep shared behavior aligned where possible, but edit the correct entrypoint
// based on which UI the user is actually running.
import { alertApi } from "../../services/api/alert.api.js";
import { renderAlertItem } from "../../dashboard/alert_box.js";
import { themeManager } from "../theme/theme.manager.js";

function _showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `alert-toast alert-toast--${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position:fixed;bottom:24px;right:24px;z-index:9999;
        padding:10px 18px;border-radius:8px;font-size:13px;font-weight:600;
        color:#fff;opacity:0;transition:opacity 0.2s;
        background:${type === 'success' ? '#16a34a' : type === 'error' ? '#dc2626' : '#2563eb'};
    `;
    document.body.appendChild(toast);
    requestAnimationFrame(() => { toast.style.opacity = '1'; });
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 200);
    }, 2500);
}

export class AlertController {
    constructor() {
        this.listElement = document.getElementById('alert-list');
        this._muteStatusEl = null;
        this._muteStateItemEl = null;
    }

    async init() {
        try {
            const res = await alertApi.getAlerts();
            const alerts = res.data || res;
            this.render(alerts);
            this._renderClearBtn();
            this._upsertMuteStateItem({ is_muted: false, mute_until: null });
            this._refreshSuggestionStatus();
            this._bindActions();
        } catch (e) {
            console.error("Alert System Offline");
        }
    }

    onNewAlert(data) {
        if (!this.listElement) return;
        if ((data.level || '').toLowerCase() === 'critical') {
            themeManager.apply('emergency');
        }
        const html = renderAlertItem(data);
        this.listElement.insertAdjacentHTML('afterbegin', html);
        this._pinMuteStateItem();
        this._bindActions();
    }

    render(alerts) {
        if (!this.listElement) return;
        this.listElement.innerHTML = alerts.map(renderAlertItem).join('');
        this._muteStateItemEl = null;
    }

    async markRead(alertId, element) {
        try {
            await alertApi.markRead(alertId);
            // Xóa alert khỏi UI sau khi ACK thành công
            element.style.transition = 'opacity 0.2s';
            element.style.opacity = '0';
            setTimeout(() => element.remove(), 200);
            _showToast('Alert acknowledged');
        } catch (e) {
            console.warn('[Alert] markRead failed', e);
            _showToast('Failed to acknowledge alert', 'error');
        }
    }

    async deleteAlert(alertId, element) {
        try {
            await alertApi.deleteAlert(alertId);
            element.style.transition = 'opacity 0.2s';
            element.style.opacity = '0';
            setTimeout(() => element.remove(), 200);
        } catch (e) {
            console.warn('[Alert] delete failed', e);
            _showToast('Failed to delete alert', 'error');
        }
    }

    async clearReadAlerts() {
        try {
            const res = await alertApi.clearReadAlerts();
            const deleted = res?.deleted ?? 0;
            this.listElement?.querySelectorAll('.alert-item.is-read').forEach(el => el.remove());
            _showToast(`Cleared ${deleted} read alert${deleted !== 1 ? 's' : ''}`);
        } catch (e) {
            console.warn('[Alert] clearRead failed', e);
            _showToast('Failed to clear alert history', 'error');
        }
    }

    async confirmSuggestedAction(deviceCode, value = 'ON') {
        try {
            await alertApi.confirmSuggestedAction({ device_code: deviceCode, value });
            _showToast(`Command sent: ${deviceCode} -> ${value}`);
        } catch (e) {
            console.warn('[Alert] confirmSuggestedAction failed', e);
            _showToast('Failed to send device command', 'error');
        }
    }

    async muteSuggestions(minutes = 60) {
        try {
            const res = await alertApi.updateSuggestionPreferences(minutes);
            const data = res?.data || {};
            const muteUntil = data?.mute_until ? new Date(data.mute_until).toLocaleTimeString() : null;
            _showToast(muteUntil ? `Suggestions muted until ${muteUntil}` : 'Suggestions unmuted');
            this._setSuggestionStatus(data);
        } catch (e) {
            console.warn('[Alert] muteSuggestions failed', e);
            _showToast('Failed to update suggestion settings', 'error');
        }
    }

    async _refreshSuggestionStatus() {
        try {
            const res = await alertApi.getSuggestionPreferences();
            this._setSuggestionStatus(res?.data || {});
        } catch (e) {
            console.warn('[Alert] getSuggestionPreferences failed', e);
        }
    }

    _setSuggestionStatus(data) {
        const isMuted = Boolean(data?.is_muted);
        if (this._muteStatusEl) {
            if (!isMuted) {
                this._muteStatusEl.textContent = 'Suggestions: ON';
            } else {
                const untilText = data?.mute_until ? new Date(data.mute_until).toLocaleTimeString() : 'later';
                this._muteStatusEl.textContent = `Suggestions muted until ${untilText}`;
            }
        }
        this._upsertMuteStateItem(data);
    }

    _renderClearBtn() {
        const container = this.listElement?.parentElement;
        if (!container || container.querySelector('.alert-clear-btn')) return;
        const btn = document.createElement('button');
        btn.className = 'alert-clear-btn';
        btn.textContent = 'Clear Read History';
        btn.style.cssText = `
            display:block;margin:8px 0;padding:6px 14px;
            font-size:12px;border:1px solid #e5e7eb;border-radius:6px;
            background:transparent;cursor:pointer;color:#6b7280;
        `;
        btn.addEventListener('click', () => this.clearReadAlerts());
        container.insertBefore(btn, this.listElement);
    }

    _upsertMuteStateItem(data) {
        if (!this.listElement) return;

        const isMuted = Boolean(data?.is_muted);
        const untilText = data?.mute_until ? new Date(data.mute_until).toLocaleTimeString() : 'later';

        if (!this._muteStateItemEl || !this._muteStateItemEl.isConnected) {
            const item = document.createElement('div');
            item.className = 'alert-item info alert-item--mute-state';
            item.setAttribute('data-bound', '1');
            item.setAttribute('data-system', 'mute-state');
            this._muteStateItemEl = item;
        }

        this._muteStateItemEl.innerHTML = `
            <span class="alert-time">[SYSTEM]</span>
            <span class="alert-msg"><strong>Suggestion Alerts:</strong> ${isMuted ? `MUTED until ${untilText}` : 'ON'}</span>
            <button class="alert-del-btn" title="Mute suggestions for 1 hour" data-action="mute-1h">Mute 1h</button>
            <button class="alert-ack-btn" title="Unmute suggestions" data-action="unmute-suggestions">Unmute</button>
            <div class="alert-scanner"></div>
        `;

        this._pinMuteStateItem();
    }

    _pinMuteStateItem() {
        if (!this.listElement || !this._muteStateItemEl) return;
        this.listElement.insertBefore(this._muteStateItemEl, this.listElement.firstChild);
    }

    _bindActions() {
        if (!this.listElement) return;
        this.listElement.querySelectorAll('.alert-item:not([data-bound])').forEach(el => {
            el.setAttribute('data-bound', '1');
            el.addEventListener('click', (e) => {
                const action = e.target.closest('[data-action]')?.getAttribute('data-action');
                if (action === 'confirm') {
                    const btn = e.target.closest('[data-device-code]');
                    const deviceCode = btn?.getAttribute('data-device-code');
                    const value = btn?.getAttribute('data-value') || 'ON';
                    if (deviceCode) this.confirmSuggestedAction(deviceCode, value);
                }
                else if (action === 'mute-1h') this.muteSuggestions(60);
                else if (action === 'unmute-suggestions') this.muteSuggestions(0);
                else {
                    const id = Number(el.getAttribute('data-id'));
                    if (!id) return;
                    if (action === 'ack') this.markRead(id, el);
                    else if (action === 'delete') this.deleteAlert(id, el);
                }
            });
        });
    }
}
export const alertController = new AlertController();