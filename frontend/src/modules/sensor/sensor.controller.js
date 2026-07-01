// src/modules/sensor/sensor.controller.js
import { renderElderlyPanel } from "../../dashboard/elderly_panel.js"; // ✅ Thêm .js

export class SensorController {
    constructor() {
        this.container = document.getElementById('elderly-display');
    }

    update(device) {
        if (!this.container) return;
        const card = document.querySelector(`[data-code="${device.code}"]`);
        if (card) {
            card.outerHTML = renderElderlyPanel(device);
        } else {
            this.container.insertAdjacentHTML('beforeend', renderElderlyPanel(device));
        }
    }
}
export const sensorController = new SensorController();