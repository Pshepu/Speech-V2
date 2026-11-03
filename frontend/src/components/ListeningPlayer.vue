<script setup lang="ts">
// Diálogos / pódcasts generados: se reproducen línea a línea con la voz de cada hablante.
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import { speak, stopSpeaking } from '../composables/audio'
import RecordButton from './RecordButton.vue'
import ClickableText from './ClickableText.vue'

const app = useApp()
const list = ref<any[]>([])
const item = ref<any>(null)
const kind = ref('dialogue')
const topic = ref('')
const level = ref(app.level)
const generating = ref(false)
const playing = ref(-1)
const rate = ref(0)
const showText = ref(false)
const answers = ref<Record<number, number>>({})
const checked = ref(false)
const retell = ref('')
const retellRes = ref<any>(null)
const evaluating = ref(false)
const transcribing = ref(false)
let stopFlag = false

const KINDS = [
  { id: 'dialogue', t: '🗣️ Diálogo' }, { id: 'podcast', t: '🎙️ Pódcast' },
  { id: 'news', t: '📻 Noticias' }, { id: 'interview', t: '🎤 Entrevista' },
]

onMounted(async () => { list.value = await api.get(`/listening/list?lang=${app.lang}`) })

async function generate() {
  generating.value = true
  try { item.value = await api.post('/listening/generate', { lang: app.lang, level: level.value, kind: kind.value, topic: topic.value || null }); reset() }
  catch (e: any) { app.notify(e.message, 'error') }
  generating.value = false
}
async function open(id: number) { item.value = await api.get(`/listening/${id}`); reset() }
function reset() { answers.value = {}; checked.value = false; retell.value = ''; retellRes.value = null; showText.value = false; playing.value = -1 }

async function playAll(from = 0) {
  stopFlag = false
  for (let i = from; i < item.value.lines.length; i++) {
    if (stopFlag) break
    playing.value = i
    const l = item.value.lines[i]
    await speak(l.t, { voice: item.value.speakers[l.speaker]?.voice, rate: rate.value })
  }
  playing.value = -1
}
function stop() { stopFlag = true; stopSpeaking(); playing.value = -1 }
function playLine(i: number) { stop(); setTimeout(() => { const l = item.value.lines[i]; playing.value = i; speak(l.t, { voice: item.value.speakers[l.speaker]?.voice, rate: rate.value }).then(() => (playing.value = -1)) }, 50) }

const score = () => {
  const qs = item.value.questions || []
  return qs.length ? Math.round((100 * qs.filter((q: any, i: number) => answers.value[i] === q.answer).length) / qs.length) : 0
}

function checkAnswers() {
  checked.value = true
  api.post('/assessment/record', { lang: app.lang, skill: 'listening', level: item.value.level, score: score() }).catch(() => {})
}

async function onSpoken(blob: Blob) {
  transcribing.value = true
  try { const r = await api.form('/stt', { audio: blob, lang: app.lang }); retell.value = (retell.value + ' ' + r.text).trim() }
  catch (e: any) { app.notify(e.message, 'error') }
  transcribing.value = false
}
async function evaluate() {
  evaluating.value = true
  try { retellRes.value = await api.post('/listening/retell', { lang: app.lang, listening_id: item.value.id, text: retell.value, source: 'retell', score: score() }) }
  catch (e: any) { app.notify(e.message, 'error') }
  evaluating.value = false
}
async function addVocab(v: any) {
  await api.post('/cards', { lang: app.lang, kind: 'phrase', front: v.t, back: v.es, source: 'listening' })
  v.added = true
}
const KIND_LABEL: Record<string, string> = { dialogue: 'Diálogo', podcast: 'Pódcast', news: 'Noticias', interview: 'Entrevista' }
</script>

<template>
  <div v-if="!item">
    <div class="card">
      <h3>Generar audio a tu nivel</h3>
      <p class="muted">Varios hablantes, acentos distintos, velocidad ajustable. Primero escucha SIN texto; luego responde, resume y, al final, mira la transcripción.</p>
      <div class="row" style="margin-bottom:10px"><button v-for="k in KINDS" :key="k.id" class="chip" :class="{ on: kind === k.id }" @click="kind = k.id">{{ k.t }}</button></div>
      <div class="row">
        <input type="text" v-model="topic" placeholder="Tema (opcional): trabajo remoto, una boda, un viaje en tren…" style="flex:1" />
        <select v-model="level" style="width:auto"><option v-for="l in app.meta.levels" :key="l">{{ l }}</option></select>
        <button class="btn primary" :disabled="generating" @click="generate"><span v-if="generating" class="spin"></span> Generar</button>
      </div>
    </div>
    <div class="card" v-if="list.length">
      <h3>Tus audios</h3>
      <button v-for="r in list" :key="r.id" class="li" @click="open(r.id)">
        <span>{{ r.done ? '✅' : '🎧' }} {{ r.title }} <small class="muted">· {{ KIND_LABEL[r.kind] }}</small></span><span class="chip">{{ r.level }}</span>
      </button>
    </div>
  </div>

  <div v-else>
    <button class="btn sm ghost" @click="stop(); item = null">← Audios</button>
    <div class="card" style="margin-top:8px">
      <div class="row between">
        <div><h2 style="margin:0">{{ showText ? item.title : '🎧 ' + KIND_LABEL[item.kind] }}</h2><small class="muted">{{ item.level }} · {{ item.speakers.map((s: any) => s.name).join(' y ') }}</small></div>
        <div class="row">
          <select v-model.number="rate" style="width:auto"><option :value="-25">🐢 Lento</option><option :value="-10">Algo lento</option><option :value="0">Normal</option><option :value="15">⚡ Rápido</option></select>
          <button v-if="playing < 0" class="btn primary" @click="playAll()">▶️ Reproducir</button>
          <button v-else class="btn" @click="stop">⏹️ Parar</button>
        </div>
      </div>
      <div class="lines">
        <div v-for="(l, i) in item.lines" :key="i" class="line" :class="{ on: playing === i }">
          <button class="btn sm ghost" @click="playLine(i)">🔊</button>
          <b class="who">{{ item.speakers[l.speaker]?.name }}:</b>
          <span v-if="showText"><ClickableText :text="l.t" /><br /><small class="muted">{{ l.es }}</small></span>
          <span v-else class="muted">{{ playing === i ? '🔊 …' : '· · ·' }}</span>
        </div>
      </div>
      <button class="btn sm" style="margin-top:10px" @click="showText = !showText">{{ showText ? '🙈 Ocultar transcripción' : '👁️ Ver transcripción' }}</button>
    </div>

    <div class="card" v-if="item.questions?.length">
      <h3>1 · Comprensión</h3>
      <div v-for="(q, i) in item.questions" :key="i" style="margin-bottom:12px">
        <b>{{ i + 1 }}. {{ q.q }}</b>
        <div class="row" style="margin-top:6px">
          <button v-for="(o, k) in q.options" :key="k" class="chip" :disabled="checked"
                  :class="checked ? (k === q.answer ? 'good' : answers[i] === k ? 'bad' : '') : answers[i] === k ? 'on' : ''" @click="answers[i] = k">{{ o }}</button>
        </div>
      </div>
      <button v-if="!checked" class="btn primary" :disabled="Object.keys(answers).length < item.questions.length" @click="checkAnswers">Comprobar</button>
      <b v-else>{{ score() }}% de comprensión</b>
    </div>

    <div class="card">
      <h3>2 · Resume lo que escuchaste</h3>
      <p class="muted">Con tus palabras, en {{ app.langInfo.name.toLowerCase() }} (escribiendo o hablando). Reutiliza expresiones que oíste.</p>
      <textarea v-model="retell" rows="4" placeholder="In this conversation…"></textarea>
      <div class="row" style="margin-top:8px">
        <RecordButton label="Dictar" :busy="transcribing" :max-seconds="90" @recorded="onSpoken" />
        <button class="btn primary" :disabled="retell.trim().length < 15 || evaluating" @click="evaluate"><span v-if="evaluating" class="spin"></span> Evaluar resumen</button>
      </div>
      <div v-if="retellRes" class="res">
        <div class="row"><span class="chip">🎯 Ideas {{ retellRes.content_score }}</span><span class="chip">✍️ Lengua {{ retellRes.language_score }}</span></div>
        <p>{{ retellRes.feedback }}</p>
        <div v-if="retellRes.missed?.length"><b>Se te escapó:</b><ul><li v-for="m in retellRes.missed" :key="m">{{ m }}</li></ul></div>
        <div v-for="(c, k) in retellRes.corrections" :key="k" class="crow"><s class="muted">{{ c.original }}</s> → <b>{{ c.corrected }}</b> <small>{{ c.explanation }}</small></div>
        <p v-if="retellRes.better"><b>Versión mejorada:</b> {{ retellRes.better }}</p>
      </div>
    </div>

    <div class="card" v-if="item.vocab?.length">
      <h3>3 · Expresiones útiles</h3>
      <div v-for="v in item.vocab" :key="v.t" class="row between crow">
        <span><b>{{ v.t }}</b> — {{ v.es }}</span>
        <button class="btn sm" :disabled="v.added" @click="addVocab(v)">{{ v.added ? '✓' : '+ Repaso' }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.li { display: flex; justify-content: space-between; width: 100%; font: inherit; color: var(--text); background: none; border: none; border-bottom: 1px solid var(--border); padding: 10px 4px; cursor: pointer; text-align: left; }
.li:hover { background: var(--surface-2); }
.lines { margin-top: 14px; display: flex; flex-direction: column; gap: 4px; }
.line { display: flex; gap: 8px; align-items: baseline; padding: 6px 8px; border-radius: 10px; }
.line.on { background: var(--accent-2); }
.who { white-space: nowrap; }
.res { margin-top: 14px; border-top: 1px solid var(--border); padding-top: 12px; }
.crow { padding: 6px 0; border-bottom: 1px solid var(--border); }
</style>
