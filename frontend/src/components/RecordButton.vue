<script setup lang="ts">
// Botón de grabar: clic para empezar, clic para parar. Muestra volumen y tiempo.
import { useRecorder } from '../composables/recorder'
import { useApp } from '../store'
import { stopSpeaking } from '../composables/audio'

const props = withDefaults(defineProps<{ disabled?: boolean; maxSeconds?: number; label?: string; busy?: boolean }>(), {
  maxSeconds: 30, label: 'Grabar',
})
const emit = defineEmits<{ (e: 'recorded', blob: Blob): void; (e: 'started'): void }>()
const rec = useRecorder()
const app = useApp()

async function toggle() {
  if (rec.recording.value) {
    const blob = await rec.stop()
    if (blob) emit('recorded', blob)
  } else {
    stopSpeaking()
    const ok = await rec.start(props.maxSeconds)
    if (!ok) app.notify(rec.error.value, 'error')
    else emit('started')
  }
}
defineExpose({ toggle, recording: rec.recording, stop: async () => { const b = await rec.stop(); if (b) emit('recorded', b) } })
</script>

<template>
  <button class="rec" :class="{ on: rec.recording.value }" :disabled="disabled || busy" @click="toggle"
          :style="{ '--lvl': Math.min(1, rec.level.value * 3) }">
    <span v-if="busy" class="spin"></span>
    <span v-else class="dot"></span>
    <span>{{ busy ? 'Analizando…' : rec.recording.value ? `Detener · ${rec.seconds.value.toFixed(1)}s` : label }}</span>
  </button>
</template>

<style scoped>
.rec { display: inline-flex; align-items: center; gap: 10px; font: inherit; font-weight: 650; font-size: 1.02rem; padding: 12px 22px; border-radius: 999px; border: none; cursor: pointer; background: var(--bad); color: #fff; box-shadow: 0 0 0 calc(var(--lvl, 0) * 14px) color-mix(in srgb, var(--bad) 25%, transparent); transition: box-shadow .08s; }
.rec:disabled { opacity: .55; cursor: not-allowed; }
.rec .dot { width: 12px; height: 12px; border-radius: 50%; background: #fff; }
.rec.on .dot { border-radius: 3px; animation: pulse 1s infinite; }
@keyframes pulse { 50% { opacity: .4; } }
</style>
