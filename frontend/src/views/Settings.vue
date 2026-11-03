<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useApp } from '../store'
import { api } from '../api'

const app = useApp()
const s = ref({ ...app.meta.settings })
const theme = ref((() => { try { return localStorage.getItem('theme') || 'auto' } catch { return 'auto' } })())
const saved = ref(false)
const facts = ref('')
onMounted(async () => { facts.value = ((await api.get('/profile')).facts || []).join('\n') })
async function saveFacts() {
  await api.put('/profile', { facts: facts.value.split('\n') })
  app.notify('Perfil guardado', 'good')
}

async function save() {
  const langChanged = s.value.lang !== app.lang
  await app.save({ lang: s.value.lang })
  await app.save({ level: s.value.level, daily_minutes: +s.value.daily_minutes, new_cards_per_day: +s.value.new_cards_per_day, speech_rate: +s.value.speech_rate })
  try {
    if (theme.value === 'auto') { localStorage.removeItem('theme'); delete document.documentElement.dataset.theme }
    else { localStorage.setItem('theme', theme.value); document.documentElement.dataset.theme = theme.value }
  } catch {}
  saved.value = true
  setTimeout(() => (saved.value = false), 2000)
  if (langChanged) location.reload()
}
const engine: Record<string, string> = { ready: '✅ Listo', loading: '⏳ Cargando (unos segundos)…', not_loaded: '⏳ Pendiente', unavailable: '⚠️ No disponible (se usa modo básico con Whisper)', disabled: 'Desactivado' }
</script>

<template>
  <div>
    <div class="page-head"><div><h1>⚙️ Ajustes</h1></div></div>
    <div class="card form">
      <label>Idioma que aprendes</label>
      <select v-model="s.lang"><option v-for="l in app.meta.languages" :key="l.code" :value="l.code">{{ l.flag }} {{ l.name }}</option></select>
      <label>Tu nivel (en {{ app.langInfo.name.toLowerCase() }})</label>
      <select v-model="s.level"><option v-for="l in app.meta.levels" :key="l">{{ l }}</option></select>
      <label>Objetivo diario (minutos)</label>
      <input type="number" v-model="s.daily_minutes" min="5" max="240" />
      <label>Palabras nuevas por día en el repaso</label>
      <input type="number" v-model="s.new_cards_per_day" min="0" max="100" />
      <small class="muted">10-20 es lo recomendable. Más palabras nuevas = muchos más repasos en los días siguientes.</small>
      <label>Velocidad de la voz</label>
      <select v-model="s.speech_rate"><option :value="-30">Lenta</option><option :value="-15">Algo lenta</option><option :value="0">Normal</option><option :value="15">Rápida</option></select>
      <label>Tema visual</label>
      <select v-model="theme"><option value="auto">Automático</option><option value="light">Claro</option><option value="dark">Oscuro</option></select>
      <div class="row" style="margin-top:8px"><button class="btn primary" @click="save">Guardar</button><span v-if="saved" class="chip good">✓ Guardado</span></div>
    </div>
    <div class="card">
      <h3>🧠 Lo que tu tutor sabe de ti</h3>
      <p class="muted">En las conversaciones el tutor recuerda datos que le contaste (trabajo, aficiones, metas) para personalizar la charla. Se escriben en el idioma que aprendes, uno por línea. Puedes editarlos o borrarlos.</p>
      <textarea v-model="facts" rows="5" placeholder="works as a nurse&#10;loves hiking&#10;wants to move to Canada"></textarea>
      <button class="btn" style="margin-top:8px" @click="saveFacts">Guardar perfil</button>
    </div>
    <div class="card">
      <h3>Estado del sistema</h3>
      <p>IA (Groq): {{ app.aiReady ? '✅ Configurada' : '❌ Falta GROQ_API_KEY en .env' }}</p>
      <p>Motor de fonemas: {{ engine[app.phonemeState] || app.phonemeState }}</p>
      <p class="muted">Contenido: {{ app.meta.content.vocab }} palabras · {{ app.meta.content.sentences }} frases · {{ app.meta.content.lessons }} lecciones · {{ app.meta.content.missions }} misiones</p>
    </div>
  </div>
</template>

<style scoped>
.form { display: grid; gap: 8px; max-width: 520px; }
.form label { margin-top: 8px; }
</style>
