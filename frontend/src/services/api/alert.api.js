// src/services/api/alert.api.js
import http from "./http.client.js"; // ✅ ĐỔI DẤU GẠCH DƯỚI THÀNH DẤU CHẤM

export const alertApi = {
    getAlerts: (limit = 50, offset = 0) => http.get(`/api/alerts/?limit=${limit}&offset=${offset}`),
    markRead: (id) => http.patch(`/api/alerts/${id}/read`),
    deleteAlert: (id) => http.delete(`/api/alerts/${id}`),
    clearReadAlerts: () => http.delete(`/api/alerts/read`),
    getSuggestionPreferences: () => http.get(`/api/alerts/suggestions/preferences`),
    updateSuggestionPreferences: (muteMinutes = 60) => http.put(`/api/alerts/suggestions/preferences`, { mute_minutes: muteMinutes }),
    confirmSuggestedAction: ({ device_code, value = 'ON' }) => http.post(`/api/alerts/confirm-action`, { device_code, value }),
};