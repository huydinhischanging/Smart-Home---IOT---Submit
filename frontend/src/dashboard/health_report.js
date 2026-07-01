// src/dashboard/health_report.js
import { ApiClient } from '../services/api_client.js';

export async function renderHealthReport() {
  try {
    const summary = await ApiClient.getHeartRateSummary();
    const avg     = summary.avg_bpm          != null ? Math.round(summary.avg_bpm)          : '--';
    const min     = summary.min_bpm          != null ? Math.round(summary.min_bpm)          : '--';
    const max     = summary.max_bpm          != null ? Math.round(summary.max_bpm)          : '--';
    const wellness = summary.normal_rate_percent != null
        ? Math.round(summary.normal_rate_percent)
        : '--';

    const avgEl      = document.getElementById('health-avg-bpm');
    const minEl      = document.getElementById('health-min-bpm');
    const maxEl      = document.getElementById('health-max-bpm');
    const wellnessEl = document.getElementById('health-wellness');

    if (avgEl)      avgEl.textContent      = avg;
    if (minEl)      minEl.textContent      = min;
    if (maxEl)      maxEl.textContent      = max;
    if (wellnessEl) wellnessEl.textContent = wellness;

    // Color-code wellness
    if (wellnessEl && typeof wellness === 'number') {
      if (wellness >= 80)      wellnessEl.style.color = 'var(--green)';
      else if (wellness >= 60) wellnessEl.style.color = '#fbbf24';
      else                     wellnessEl.style.color = 'var(--red)';
    }

    // Color-code average BPM
    if (avgEl && typeof avg === 'number') {
      if (avg >= 60 && avg <= 100) avgEl.style.color = 'var(--accent)';
      else                         avgEl.style.color = 'var(--red)';
    }
  } catch (err) {
    console.warn('[HealthReport] Failed to load summary:', err);
  }
}
