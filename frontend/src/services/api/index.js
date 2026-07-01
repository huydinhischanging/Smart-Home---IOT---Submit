// src/services/api/index.js
// Responsibility: Public API client facade (Bat-Computer Access Point)

import { DeviceApi } from './device.api.js'
import { BrokerApi } from './broker.api.js'
import { alertApi } from './alert.api.js' // ✅ Import thêm Alert API vừa tạo
import { AIApi } from './ai.api.js' // ✅ AI chat API

export const ApiClient = {
  ...DeviceApi,
  ...BrokerApi,
  ...alertApi,
  ...AIApi
}