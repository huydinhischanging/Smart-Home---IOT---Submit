// src/services/api/broker.api.js
// Responsibility: MQTT broker config API

import { HttpClient } from './http.client.js'

export const BrokerApi = {
  getConfig() {
    return HttpClient.get('/api/broker-config')
  },

  saveConfig(config) {
    return HttpClient.post('/api/broker-config', config)
  }
}
