// src/dashboard/print_report.js
import { ApiClient } from '../services/api_client.js';

export async function printHealthReport() {
  // 1. Lấy dữ liệu hồ sơ bệnh nhân
  const profile = await ApiClient.getPatientProfile();
  // 2. Lấy dữ liệu tổng hợp chỉ số sinh tồn
  const summary = await ApiClient.getHeartRateSummary();
  // 3. Lấy ngày giờ hiện tại
  const now = new Date();
  const dateStr = now.toLocaleDateString();

  // 4. Nhận xét AI (giả lập, có thể lấy từ backend nếu có)
  let aiComment = 'All vital signs are within normal range.';
  if (summary.critical > 0) aiComment = 'Warning: Critical heart rate events detected!';
  else if (summary.caution > 0) aiComment = 'Caution: Some values outside optimal range.';

  // 5. Tạo HTML report
  const html = `
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:auto;">
      <h2 style="text-align:center;">Patient Health Report</h2>
      <div style="margin-bottom:16px;">
        <b>Name:</b> ${profile.patient_name || '--'}<br>
        <b>Age:</b> ${profile.age || '--'}<br>
        <b>Gender:</b> ${profile.gender || '--'}<br>
        <b>Date:</b> ${dateStr}
      </div>
      <h3>Vital Signs Summary</h3>
      <table style="width:100%;border-collapse:collapse;">
        <tr><th style="border:1px solid #ccc;padding:4px;">Avg BPM</th><th style="border:1px solid #ccc;padding:4px;">Min BPM</th><th style="border:1px solid #ccc;padding:4px;">Max BPM</th><th style="border:1px solid #ccc;padding:4px;">Wellness (%)</th></tr>
        <tr><td style="border:1px solid #ccc;padding:4px;">${summary.avg_bpm ?? '--'}</td><td style="border:1px solid #ccc;padding:4px;">${summary.min_bpm ?? '--'}</td><td style="border:1px solid #ccc;padding:4px;">${summary.max_bpm ?? '--'}</td><td style="border:1px solid #ccc;padding:4px;">${summary.normal_rate_percent ?? '--'}</td></tr>
      </table>
      <h3>AI Assessment</h3>
      <div style="margin-bottom:16px;">${aiComment}</div>
      <h3>Alert History</h3>
      <div><b>Critical:</b> ${summary.severity_counts?.critical ?? 0} | <b>Caution:</b> ${summary.severity_counts?.caution ?? 0} | <b>Normal:</b> ${summary.severity_counts?.normal ?? 0}</div>
    </div>
  `;

  // 6. In report (mở popup print chỉ phần report)
  const printWindow = window.open('', '', 'width=800,height=900');
  printWindow.document.write('<html><head><title>Patient Health Report</title></head><body>' + html + '</body></html>');
  printWindow.document.close();
  printWindow.focus();
  setTimeout(() => printWindow.print(), 500);
}
