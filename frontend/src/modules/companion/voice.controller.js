// src/modules/companion/voice.controller.js

const LANG_VI = 'vi-VN'
const LANG_EN = 'en-US'

class VoiceController {
    constructor() {
        this._recognition = null
        this._isListening = false
        this._lang = localStorage.getItem('voice_lang') || LANG_VI
    }

    _isSupported() {
        return typeof window !== 'undefined' &&
            ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)
    }

    _createRecognition() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition
        const rec = new SR()
        rec.lang = this._lang
        rec.interimResults = false
        rec.maxAlternatives = 1
        rec.continuous = false

        rec.onstart = () => {
            this._isListening = true
            this._setMicState('listening')
            const label = this._lang === LANG_VI ? 'VI' : 'EN'
            this._showToast('Dang nghe [' + label + ']... Hay noi lenh')
        }

        rec.onresult = (event) => {
            const transcript = event.results[0][0].transcript.trim()
            console.log('[Voice] Got:', transcript)
            this._injectAndSend(transcript)
        }

        rec.onerror = (event) => {
            console.warn('[Voice] Error:', event.error)
            const msgs = {
                'not-allowed'  : 'Trinh duyet chan mic! Cho phep mic trong thanh dia chi.',
                'no-speech'    : 'Khong nghe thay giong noi. Thu lai.',
                'network'      : 'Loi mang. Web Speech can HTTPS hoac localhost.',
                'audio-capture': 'Khong tim thay mic. Kiem tra thiet bi.',
                'aborted'      : ''
            }
            const msg = msgs[event.error] ?? 'Loi: ' + event.error
            if (msg) this._showToast(msg)
            this._setMicState('idle')
            this._isListening = false
        }

        rec.onend = () => {
            this._isListening = false
            this._setMicState('idle')
        }

        return rec
    }

    _injectAndSend(text) {
        const alfredInput = document.getElementById('alfred-win-input')
        if (alfredInput) {
            alfredInput.value = text
            alfredInput.dispatchEvent(new Event('input'))
            const alfredWin = document.getElementById('alfred-window')
            if (alfredWin && alfredWin.classList.contains('hidden')) {
                if (typeof window.toggleAlfred === 'function') window.toggleAlfred()
            }
            setTimeout(() => {
                if (typeof window.sendAlfredChat === 'function') {
                    window.sendAlfredChat()
                } else {
                    document.getElementById('alfred-win-send')?.click()
                }
            }, 150)
            return
        }
        const chatInput = document.getElementById('chat-message')
        if (chatInput) {
            chatInput.value = text
            chatInput.dispatchEvent(new Event('input'))
            setTimeout(() => document.getElementById('chat-send')?.click(), 150)
        }
    }

    sendCommand(text) {
        this._injectAndSend(text)
    }

    _setMicState(state) {
        const btn = document.getElementById('voice-mic-btn')
        if (!btn) return
        if (state === 'listening') {
            btn.classList.add('mic-active')
            btn.title = 'Dang nghe... (click de dung)'
        } else {
            btn.classList.remove('mic-active')
            btn.title = 'Nhan de noi lenh'
        }
    }

    _showToast(msg) {
        let toast = document.getElementById('voice-toast')
        if (!toast) {
            toast = document.createElement('div')
            toast.id = 'voice-toast'
            document.body.appendChild(toast)
        }
        toast.textContent = msg
        toast.classList.add('show')
        clearTimeout(this._toastTimer)
        this._toastTimer = setTimeout(() => toast.classList.remove('show'), 3000)
    }

    toggleLang() {
        this._lang = this._lang === LANG_VI ? LANG_EN : LANG_VI
        localStorage.setItem('voice_lang', this._lang)
        const label = this._lang === LANG_VI ? 'VI' : 'EN'
        const langEl = document.getElementById('voice-lang-label')
        if (langEl) langEl.textContent = label
        this._showToast('Switch: ' + label + (this._lang === LANG_EN ? ' (English)' : ' (Tieng Viet)'))
    }

    start() {
        if (!this._isSupported()) {
            this._showToast('Trinh duyet khong ho tro. Dung Chrome hoac Edge.')
            return
        }
        if (this._isListening) {
            this.stop()
            return
        }
        // Feedback ngay lập tức — không chờ onstart
        const label = this._lang === LANG_VI ? 'VI' : 'EN'
        this._showToast('Dang khoi dong mic [' + label + ']...')
        this._setMicState('listening')
        this._isListening = true
        this._recognition = this._createRecognition()
        try {
            this._recognition.start()
        } catch (e) {
            console.warn('[Voice] start error:', e)
            this._showToast('Loi: ' + e.message)
            this._setMicState('idle')
            this._isListening = false
        }
    }

    stop() {
        if (this._recognition) this._recognition.stop()
        this._isListening = false
        this._setMicState('idle')
    }

    init() {
        const micBtn = document.getElementById('voice-mic-btn')
        const langBtn = document.getElementById('voice-lang-btn')
        const langLabel = document.getElementById('voice-lang-label')

        if (!micBtn) {
            console.warn('[Voice] #voice-mic-btn not found in DOM')
            return
        }

        if (langLabel) langLabel.textContent = this._lang === LANG_VI ? 'VI' : 'EN'

        const supported = this._isSupported()
        console.log('[Voice] supported:', supported, '| lang:', this._lang)

        if (!supported) {
            micBtn.style.opacity = '0.4'
            micBtn.style.cursor = 'not-allowed'
            micBtn.title = 'Dung Chrome/Edge'
        }

        // onclick attrs handle clicks — no addEventListener needed
        console.log('[Voice] Ready, lang:', this._lang, '| supported:', this._isSupported())
    }

    mount(_selector) { this.init() }
}

export const voiceController = new VoiceController()