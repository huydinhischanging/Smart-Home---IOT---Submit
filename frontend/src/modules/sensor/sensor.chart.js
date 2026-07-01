// src/modules/sensor/sensor.chart.js
export class BatECG {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.points = new Array(100).fill(50); // Mảng lưu trữ các điểm sóng
    }

    // Vẽ sóng giả lập dựa trên nhịp tim thật
    draw(heartRate) {
        if (!this.ctx) return;
        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;
        
        // Thêm điểm mới dựa trên nhịp tim (càng cao sóng càng nhọn)
        const amplitude = heartRate > 100 ? 40 : 20;
        const newPoint = 50 + (Math.random() - 0.5) * amplitude;
        this.points.push(newPoint);
        this.points.shift();

        ctx.clearRect(0, 0, width, height);
        ctx.beginPath();
        ctx.strokeStyle = heartRate > 120 ? '#ff0000' : '#4ade80'; // Đỏ nếu cao, xanh nếu ổn
        ctx.lineWidth = 2;
        ctx.shadowBlur = 10;
        ctx.shadowColor = ctx.strokeStyle;

        for (let i = 0; i < this.points.length; i++) {
            const x = (i / this.points.length) * width;
            const y = (this.points[i] / 100) * height;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();
    }
}