export class NotificationManager {
    static notify(title, message, type = 'info') {
        const drawer = document.getElementById('notification-drawer') || this.createDrawer();
        const icon = type === 'critical' ? '🚨' : '🤖';
        const html = `
            <div class="bat-toast ${type}">
                <div class="toast-content">
                    <b>${icon} ${title}</b>
                    <p>${message}</p>
                </div>
            </div>
        `;
        drawer.insertAdjacentHTML('afterbegin', html);
        // Tự biến mất sau 5 giây
        setTimeout(() => {
            drawer.lastElementChild?.remove();
        }, 5000);
    }

    static createDrawer() {
        const div = document.createElement('div');
        div.id = 'notification-drawer';
        div.className = 'toast-container';
        document.body.appendChild(div);
        return div;
    }
}