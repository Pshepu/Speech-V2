// Reproducción de voz (TTS del backend) con caché de URLs.
import { ref } from 'vue'
import { useApp } from '../store'

const cache = new Map<string, string>()
let current: HTMLAudioElement | null = null
export const speaking = ref('')

export async function speak(
  text: string,
  opts: { lang?: string; voice?: string; rate?: number; random?: boolean } = {},
) {
  const t = (text || '').trim()
  if (!t) return
  const app = useApp()
  const lang = opts.lang || app.lang
  const rate = opts.rate ?? (app.meta?.settings?.speech_rate || 0)
  const key = `${lang}|${opts.voice || ''}|${rate}|${opts.random ? Math.random() : ''}|${t}`
  stopSpeaking()
  speaking.value = t
  try {
    let url = cache.get(key)
    if (!url) {
      const res = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ text: t, lang, voice: opts.voice, rate, random_voice: !!opts.random }),
      })
      if (!res.ok) throw new Error('tts')
      url = URL.createObjectURL(await res.blob())
      if (!opts.random) cache.set(key, url)
    }
    const a = new Audio(url)
    current = a
    await new Promise<void>((resolve) => {
      a.onended = () => resolve()
      a.onerror = () => resolve()
      a.play().catch(() => resolve())
    })
  } catch (e) {
    app.notify('No se pudo reproducir el audio (¿hay conexión a internet?)', 'error')
  } finally {
    if (speaking.value === t) speaking.value = ''
  }
}

export function stopSpeaking() {
  if (current) {
    current.pause()
    current = null
  }
  speaking.value = ''
}

export function playBlob(blob: Blob) {
  stopSpeaking()
  const a = new Audio(URL.createObjectURL(blob))
  current = a
  a.play()
}
