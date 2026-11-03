<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import { speak } from '../composables/audio'
import RecordButton from '../components/RecordButton.vue'
import PlayButton from '../components/PlayButton.vue'

const app = useApp()
const tab = ref<'reading' | 't432' | 'rapid'>('reading')

// ---- Lectura repetida cronometrada ----
const sentence = ref<any>(null)
const wpms = ref<number[]>([])
const scores = ref<number[]>([])
const busy = ref(false)
async function newSentence() {
  wpms.value = []; scores.value = []
  const lvls = app.meta.levels
  const lvl = lvls[Math.max(0, lvls.indexOf(app.level) - 1)] // material algo más fácil que tu nivel
  sentence.value = await api.get(`/practice/sentence?lang=${app.lang}&level=${lvl}`)
}
newSentence()
async function onReading(blob: Blob) {
  busy.value = true
  try {
    const r = await api.form('/practice/assess', { audio: blob, text: sentence.value.text, lang: app.lang, mode: 'fluency' })
    wpms.value.push(r.fluency?.wpm || 0)
    scores.value.push(r.score)
    if (wpms.value.length === 3) api.post('/fluency/record', { lang: app.lang, kind: 'repeated_reading', data: { text: sentence.value.text, wpm: wpms.value, scores: scores.value }, minutes: 2 })
  } catch (e: any) { app.notify(e.message, 'error') }
  busy.value = false
}

// ---- 4/3/2 ----
const TOPICS = ref<string[]>([])
api.get('/fluency/topics').then((t) => (TOPICS.value = t))
const topic = ref('')
const ROUNDS = [240, 180, 120]
const round = ref(0)
const remaining = ref(0)
const results = ref<any[]>([])
const recRef = ref<any>(null)
const t432busy = ref(false)
let timer: any = null
function startTopic() {
  topic.value = TOPICS.value[Math.floor(Math.random() * TOPICS.value.length)]
  round.value = 0; results.value = []
}
function onStarted() {
  if (tab.value !== 't432') return
  remaining.value = ROUNDS[round.value]
  timer = setInterval(() => {
    remaining.value--
    if (remaining.value <= 0) { clearInterval(timer); recRef.value?.stop() }
  }, 1000)
}
async function on432(blob: Blob) {
  clearInterval(timer)
  t432busy.value = true
  try {
    const r = await api.form('/fluency/speech', { audio: blob, lang: app.lang })
    results.value.push(r)
    round.value++
    if (round.value === 3) api.post('/fluency/record', { lang: app.lang, kind: 'four_three_two', data: { topic: topic.value, rounds: results.value.map((x) => ({ words: x.words, wpm: x.wpm })) }, minutes: 9 })
  } catch (e: any) { app.notify(e.message, 'error') }
  t432busy.value = false
}
onBeforeUnmount(() => clearInterval(timer))
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

// ---- Repaso rápido ----
const mastered = ref<any[]>([])
const ri = ref(0)
const revealed = ref(false)
let rtimer: any = null
async function startRapid() {
  mastered.value = (await api.get(`/fluency/mastered?lang=${app.lang}`)).sort(() => Math.random() - 0.5)
  ri.value = 0; showRapid()
}
function showRapid() {
  revealed.value = false
  clearTimeout(rtimer)
  const c = mastered.value[ri.value]
  if (!c) return
  rtimer = setTimeout(() => { revealed.value = true; speak(c.front) }, 2500)
}
function nextRapid() {
  ri.value++
  if (ri.value >= mastered.value.length) api.post('/fluency/record', { lang: app.lang, kind: 'rapid_review', data: { count: mastered.value.length }, minutes: 2 })
  else showRapid()
}
</script>

<template>
  <div>
    <div class="page-head">
      <div><h1>⚡ Fluidez</h1><p>La 4ª vertiente de Paul Nation: hablar más rápido y con menos pausas usando material que ya conoces, con presión de tiempo.</p></div>
    </div>
    <div class="tabs">
      <button :class="{ on: tab === 'reading' }" @click="tab = 'reading'">Lectura repetida</button>
      <button :class="{ on: tab === 't432' }" @click="tab = 't432'">Técnica 4/3/2</button>
      <button :class="{ on: tab === 'rapid' }" @click="tab = 'rapid'; startRapid()">Repaso rápido</button>
    </div>

    <div v-if="tab === 'reading' && sentence" class="card">
      <p class="muted">Lee la misma frase 3 veces seguidas, intentando ir más rápido y fluido cada vez sin perder claridad.</p>
      <div class="big-text">{{ sentence.text }}</div>
      <small class="muted">{{ sentence.translation }}</small>
      <div class="row" style="margin-top:16px">
        <PlayButton :text="sentence.text" label="Modelo" size="" />
        <RecordButton v-if="wpms.length < 3" :busy="busy" :label="`Lectura ${wpms.length + 1}/3`" @recorded="onReading" />
        <button v-else class="btn primary" @click="newSentence">Otra frase →</button>
      </div>
      <div v-if="wpms.length" class="bars">
        <div v-for="(w, i) in wpms" :key="i" class="barcol">
          <div class="bar" :style="{ height: Math.min(100, w / 2) + '%' }"><b>{{ w }}</b></div>
          <small>#{{ i + 1 }} · {{ Math.round(scores[i]) }}pts</small>
        </div>
      </div>
      <p v-if="wpms.length === 3" class="muted">{{ wpms[2] > wpms[0] ? `¡+${wpms[2] - wpms[0]} palabras/min de la 1ª a la 3ª! 🚀` : 'Intenta soltarte más en cada repetición.' }}</p>
    </div>

    <div v-if="tab === 't432'" class="card">
      <p class="muted">Habla del mismo tema 3 veces: 4 minutos, luego 3, luego 2. Al repetir con menos tiempo, tu cerebro automatiza las frases y ganas velocidad.</p>
      <button v-if="!topic" class="btn primary" @click="startTopic">🎲 Elegir tema</button>
      <template v-else>
        <h2>🗣️ {{ topic }}</h2>
        <small class="muted">Háblalo en {{ app.langInfo.name.toLowerCase() }}. No pares aunque te equivoques.</small>
        <div v-if="round < 3" class="row" style="margin-top:16px">
          <div class="timer">{{ fmt(remaining || ROUNDS[round]) }}</div>
          <RecordButton ref="recRef" :busy="t432busy" :max-seconds="ROUNDS[round] + 2" :label="`Ronda ${round + 1}: ${ROUNDS[round] / 60} min`" @started="onStarted" @recorded="on432" />
        </div>
        <div v-if="results.length" class="stack" style="margin-top:16px">
          <div v-for="(r, i) in results" :key="i" class="card flat">
            <b>Ronda {{ i + 1 }} ({{ ROUNDS[i] / 60 }} min):</b> {{ r.words }} palabras · {{ r.wpm }} palabras/min · {{ r.long_pauses }} pausas largas
            <details><summary class="muted">Transcripción</summary><p>{{ r.text }}</p></details>
          </div>
        </div>
        <div v-if="round === 3" class="row" style="margin-top:12px">
          <b>{{ results[2].wpm > results[0].wpm ? `🚀 Velocidad: ${results[0].wpm} → ${results[2].wpm} palabras/min` : 'Sigue practicando: la clave es repetir el mismo contenido más rápido.' }}</b>
          <button class="btn" @click="startTopic">Otro tema</button>
        </div>
      </template>
    </div>

    <div v-if="tab === 'rapid'" class="card center">
      <template v-if="!mastered.length"><p class="muted">Todavía no tienes tarjetas bien asentadas (estabilidad ≥ 10 días). Sigue con el repaso diario y vuelve en unos días.</p></template>
      <template v-else-if="ri < mastered.length">
        <small class="muted">{{ ri + 1 }}/{{ mastered.length }} · di la traducción en voz alta antes de que aparezca (2,5 s)</small>
        <div class="big-text" style="margin:30px 0 10px">{{ mastered[ri].kind === 'word' ? mastered[ri].back : mastered[ri].back }}</div>
        <div class="big-text score-good" :style="{ visibility: revealed ? 'visible' : 'hidden' }">{{ mastered[ri].front }}</div>
        <button class="btn primary" style="margin-top:20px" @click="nextRapid">Siguiente →</button>
      </template>
      <template v-else><h2>⚡ ¡Hecho!</h2><button class="btn" @click="startRapid">Otra vez</button></template>
    </div>
  </div>
</template>

<style scoped>
.bars { display: flex; gap: 16px; align-items: flex-end; height: 160px; margin-top: 20px; }
.barcol { display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; gap: 4px; }
.bar { width: 56px; background: var(--accent); border-radius: 8px 8px 0 0; display: flex; justify-content: center; color: var(--accent-text); padding-top: 4px; min-height: 24px; transition: height .5s; }
.timer { font-family: var(--mono); font-size: 2rem; font-weight: 700; }
.center { text-align: center; }
</style>
