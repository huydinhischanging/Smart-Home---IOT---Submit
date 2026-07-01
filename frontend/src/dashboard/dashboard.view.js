// src/dashboard/dashboard.view.js
export function renderDashboard(app) {
  app.innerHTML = `

  <!-- HEALTH REPORT PANEL -->
  <section class="panel health-report-panel">
    <div class="panel-header">
      <div class="panel-title">
        <span>🩺</span>
        <h2>BÁO CÁO SỨC KHỎE</h2>
        <div class="panel-dot"></div>
      </div>
      <button class="btn" id="printReportBtn">🖨️ In báo cáo</button>
    </div>
    <div class="panel-body">
      <div class="health-report-grid">
        <div class="health-report-card">
          <div class="health-report-card-icon">❤️</div>
          <label>Nhịp Tim TB</label>
          <div id="health-avg-bpm" class="health-report-val">--</div>
          <div class="health-report-unit">BPM</div>
        </div>
        <div class="health-report-card">
          <div class="health-report-card-icon">📉</div>
          <label>Thấp nhất</label>
          <div id="health-min-bpm" class="health-report-val health-report-val--low">--</div>
          <div class="health-report-unit">BPM</div>
        </div>
        <div class="health-report-card">
          <div class="health-report-card-icon">📈</div>
          <label>Cao nhất</label>
          <div id="health-max-bpm" class="health-report-val health-report-val--high">--</div>
          <div class="health-report-unit">BPM</div>
        </div>
        <div class="health-report-card health-report-card--wellness">
          <div class="health-report-card-icon">💚</div>
          <label>Chỉ số khỏe</label>
          <div id="health-wellness" class="health-report-val health-report-val--wellness">--</div>
          <div class="health-report-unit">%</div>
        </div>
      </div>
    </div>
  </section>

  <!-- DEVICES PANEL -->
  <section class="panel devices-panel">
    <div class="panel-header">
      <div class="panel-title">
        <span>📟</span>
        <h2>THIẾT BỊ</h2>
        <div class="panel-dot"></div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">
        <button class="btn-ghost" id="toggleDevicesBtn">📂 Mở / Đóng</button>
        <button class="btn" onclick="openAddDeviceModal()">＋ Thêm thiết bị</button>
      </div>
    </div>
    <div id="device-folder" class="devices-container">
      <div class="folder-header" onclick="toggleDeviceFolder()">
        📂 Danh sách thiết bị
        <span class="folder-toggle">▾</span>
      </div>
      <div class="folder-devices" id="folder-devices"></div>
    </div>
  </section>

  <!-- EEG PANEL (legacy, kept for compatibility) -->
  <section class="panel eeg-panel" style="display:none;">
    <div id="eeg_chart_div" style="width:100%; height:300px;"></div>
  </section>

`;
}
