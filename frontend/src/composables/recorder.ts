// Grabación de micrófono a WAV 16 kHz mono (lo que espera el backend), sin librerías.
import { ref, onBeforeUnmount } from 'vue'

const WORKLET = `
class Rec extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0]
    if (ch) this.port.postMessage(ch.slice(0))
    return true
  }
}
registerProcessor('rec-proc', Rec)
`

function encodeWav(chunks: Float32Array[], sampleRate: number): Blob {
  const length = chunks.reduce((n, c) => n + c.length, 0)
  const buffer = new ArrayBuffer(44 + length * 2)
  const view = new DataView(buffer)
  const write = (o: number, s: string) => [...s].forEach((c, i) => view.setUint8(o + i, c.charCodeAt(0)))
  write(0, 'RIFF'); view.setUint32(4, 36 + length * 2, true); write(8, 'WAVE')
  write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true); view.setUint16(34, 16, true)
  write(36, 'data'); view.setUint32(40, length * 2, true)
  let o = 44
  for (const c of chunks) {
    for (let i = 0; i < c.length; i++, o += 2) {
      const s = Math.max(-1, Math.min(1, c[i]))
      view.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

function downsample(data: Float32Array, from: number, to: number): Float32Array {
  if (from === to) return data
  const ratio = from / to
  const out = new Float32Array(Math.floor(data.length / ratio))
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(data.length, Math.floor((i + 1) * ratio))
    let sum = 0
    for (let j = start; j < end; j++) sum += data[j]
    out[i] = sum / Math.max(1, end - start)
  }
  return out
}

export function useRecorder() {
  const recording = ref(false)
  const level = ref(0) // volumen 0-1 para el medidor
  const seconds = ref(0)
  const error = ref('')
  let ctx: AudioContext | null = null
  let stream: MediaStream | null = null
  let node: AudioWorkletNode | ScriptProcessorNode | null = null
  let chunks: Float32Array[] = []
  let timer: any = null
  let resolveStop: ((b: Blob | null) => void) | null = null
  let maxTimer: any = null

  // autoStop: para solo cuando, después de hablar, hay ~1,3 s de silencio (modo manos libres).
  async function start(maxSeconds = 30, autoStop?: () => void): Promise<boolean> {
    if (recording.value) return false
    error.value = ''
    chunks = []
    let spoke = false
    let lastVoice = 0
    let noiseFloor = 0.01
    const startedAt = Date.now()
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
    } catch (e) {
      error.value = 'No se pudo acceder al micrófono. Revisa los permisos del navegador.'
      return false
    }
    try {
      ctx = new AudioContext({ sampleRate: 16000 })
    } catch {
      ctx = new AudioContext()
    }
    const src = ctx.createMediaStreamSource(stream)
    const onData = (d: Float32Array) => {
      chunks.push(d)
      let peak = 0
      for (let i = 0; i < d.length; i += 8) peak = Math.max(peak, Math.abs(d[i]))
      level.value = level.value * 0.7 + peak * 0.3
      if (autoStop) {
        const now = Date.now()
        if (now - startedAt < 400) noiseFloor = Math.max(noiseFloor, peak) // ruido de fondo inicial
        const thr = Math.max(0.035, noiseFloor * 2.5)
        if (peak > thr) { spoke = true; lastVoice = now }
        else if (spoke && now - lastVoice > 1300 && recording.value) autoStop()
      }
    }
    try {
      const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }))
      await ctx.audioWorklet.addModule(url)
      const w = new AudioWorkletNode(ctx, 'rec-proc')
      w.port.onmessage = (e) => onData(e.data)
      src.connect(w)
      node = w
    } catch {
      const sp = ctx.createScriptProcessor(4096, 1, 1)
      sp.onaudioprocess = (e) => onData(new Float32Array(e.inputBuffer.getChannelData(0)))
      src.connect(sp)
      sp.connect(ctx.destination)
      node = sp
    }
    recording.value = true
    seconds.value = 0
    timer = setInterval(() => (seconds.value += 0.1), 100)
    maxTimer = setTimeout(() => stop(), maxSeconds * 1000)
    return true
  }

  function stop(): Promise<Blob | null> {
    return new Promise((resolve) => {
      if (!recording.value || !ctx) return resolve(null)
      resolveStop = resolve
      clearInterval(timer)
      clearTimeout(maxTimer)
      const rate = ctx.sampleRate
      try { node?.disconnect() } catch {}
      stream?.getTracks().forEach((t) => t.stop())
      ctx.close()
      recording.value = false
      level.value = 0
      const joined = new Float32Array(chunks.reduce((n, c) => n + c.length, 0))
      let o = 0
      for (const c of chunks) { joined.set(c, o); o += c.length }
      const blob = encodeWav([downsample(joined, rate, 16000)], 16000)
      ctx = null
      resolveStop?.(blob)
    })
  }

  onBeforeUnmount(() => { if (recording.value) stop() })
  return { recording, level, seconds, error, start, stop }
}
