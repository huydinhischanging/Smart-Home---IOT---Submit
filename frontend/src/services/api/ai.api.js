// src/services/api/ai.api.js
import { HttpClient } from './http.client.js'

export const AIApi = {
  status: () => HttpClient.get('/api/ai/status'),

  chat: ({ message, mode = 'llm', context = null }) => {
    if (!message || typeof message !== 'string') {
      throw new Error('message is required for AI chat')
    }

    return HttpClient.post('/api/ai/chat', {
      message: message.trim(),
      mode,
      context
    })
  }
}

export default AIApi
