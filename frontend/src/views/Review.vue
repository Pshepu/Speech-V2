<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import { speak } from '../composables/audio'
import PlayButton from '../components/PlayButton.vue'
import RecordButton from '../components/RecordButton.vue'

const app = useApp()
const queue = ref<any[]>([])
const info = ref<any>(null)
const flipped = ref(false)
const done = ref(0)
const loading = ref(true)
const started = ref(Date.now())
const typed = ref('')
const adding = ref(false)
const mnemonic = ref('')
const mnemonicLoading = ref(false)
const listening = ref(false)

async function load() {
  loading.value = true
  info.value = await api.get(`/srs/queue?lang=${app.lang}`)
  queue.value = info.value.cards
  loading.value = false
  resetCard()
}
onMounted(() => { load(); window.addEventListener('keydown', onKey) })
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

const current = computed(() => queue.value[0])

// Modo de la tarjeta:
//  - recognition: ves la palabra y recuerdas el significado (palabras nuevas).
//  - cloze: completas la palabra en una frase (palabras ya en repaso: de reconocer a PRODUCIR).
//  - production: ves el significado en español y dices la expresión (frases y expresiones).
//  - mistake: corriges tu propio error.
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const clozeText = computed(() => {
  const c = current.value
  if (!c || c.kind !== 'word' || !c.extra?.example) return null
  const re = new RegExp(`\\b${esc(c.front)}\\b`, 'i')
  return re.test(c.extra.example) ? c.extra.example.replace(re, '_____') : null
})
const mode = computed(() => {
  const c = current.value
  if (!c) return ''
  if (c.kind === 'mistake') return 'mistake'
  if (c.kind === 'phrase' || c.kind === 'sentence') return 'production'
  if (c.state === 2 && clozeText.value) return 'cloze'
  return 'recognition'
})
const norm = (s: string) => (s || '').toLowerCase().replace(/[’]/g, "'").replace(/[^\p{L}\p{N}' ]/gu, '').replace(/\s+/g, ' ').trim()
const typedOk = computed(() => {
  if (!typed.value.trim() || !current.value) return null
  const target = mode.value === 'mistake' ? current.value.back : current.value.front
  return norm(typed.value) === norm(target)
})

function resetCard() {
  flipped.value = false
  typed.value = ''
  mnemonic.value = current.value?.extra?.mnemonic || ''
  started.value = Date.now()
  if (current.value && mode.value === 'recognition') speak(current.value.front)
}

function flip() {
  flipped.value = true
  const c = current.value
  if (mode.value === 'mistake') speak(c.back)
  else if (mode.value === 'production') speak(c.front)
  else if (mode.value === 'cloze') speak(c.extra.example)
}

async function rate(r: string) {
  const c = current.value
  if (!c) return
  const seconds = (Date.now() - started.value) / 1000
  queue.value.shift()
  done.value++
  // "Otra vez" la vuelve a mostrar en esta misma sesión (paso de aprendizaje).
  if (r === 'again') queue.value.splice(Math.min(4, queue.value.length), 0, c)
  api.post('/srs/review', { card_id: c.id, rating: r, seconds }).catch(() => {})
  resetCard()
}

async function getMnemonic() {
  mnemonicLoading.value = true
  try {
    const r = await api.post(`/cards/${current.value.id}/mnemonic`)
    mnemonic.value = r.mnemonic
    current.value.extra = { ...current.value.extra, mnemonic: r.mnemonic }
  } catch (e: any) { app.notify(e.message, 'error') }
  mnemonicLoading.value = false
}

async function onSpoken(blob: Blob) {
  listening.value = true
  try {
    const r = await api.form('/stt', { audio: blob, lang: app.lang })
    typed.value = r.text.replace(/[.!?]$/, '')
  } catch (e: any) { app.notify(e.message, 'error') }
  listening.value = false
}

async function addMore(n: number) {
  adding.value = true
  const r = await api.post('/cards/bulk', { lang: app.lang, count: n })
  app.notify(`${r.added} palabras nuevas añadidas`, 'good')
  adding.value = false
  load()
}

async function suspend() {
  await api.del(`/cards/${current.value.id}`)
  queue.value.shift()
  resetCard()
}

function onKey(e: KeyboardEvent) {
  if ((e.target as HTMLElement)?.tagName === 'INPUT') { if (e.key === 'Enter' && !flipped.value) { e.preventDefault(); flip() } return }
  if (!current.value) return
  if (!flipped.value && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); flip() }
  else if (flipped.value) {
    const map: any = { '1': 'again', '2': 'hard', '3': 'good', '4': 'easy', ' ': 'good' }
    if (map[e.key]) { e.preventDefault(); rate(map[e.key]) }
  }
}
const KIND: Record<string, string> = { recognition: 'Palabra', cloze: 'Completa la frase', production: 'Expresión', mistake: 'Tu error' }
</script>

<template>
  <div>
    <div class="page-head">
      <div><h1>🧠 Repaso espaciado</h1><p>Algoritmo FSRS: cada tarjeta vuelve justo antes de que la olvides. Intenta recordar ANTES de girarla.</p></div>
      <div class="row" v-if="info">
        <span class="chip">📌 {{ info.due }} pendientes</span>
        <span class="chip">🆕 {{ info.new_left_today }} nuevas hoy</span>
        <span class="chip">🗂️ {{ info.total }} en el mazo</span>
      </div>
    </div>

    <div v-if="loading" class="empty"><span class="spin"></span></div>
    <div v-else-if="current" class="card flash">
      <div class="row between">
        <span class="chip" :class="mode === 'mistake' ? 'bad' : mode === 'cloze' || mode === 'production' ? 'mission' : 'on'">{{ KIND[mode] }}</span>
        <div class="row"><small class="muted">{{ done }} repasadas · {{ queue.length }} quedan</small>
          <button class="btn sm ghost" title="No volver a mostrar" @click="suspend">🗑️</button></div>
      </div>

      <div class="face">
        <template v-if="mode === 'mistake'">
          <small class="muted">¿Cómo se dice correctamente?</small>
          <div class="big-text"><s class="muted">{{ current.front }}</s></div>
        </template>
        <template v-else-if="mode === 'production'">
          <small class="muted">¿Cómo se dice en {{ app.langInfo.name.toLowerCase() }}?</small>
          <div class="big-text">🇪🇸 {{ current.back }}</div>
          <small v-if="current.extra?.example_es" class="muted">Ej.: {{ current.extra.example_es }}</small>
        </template>
        <template v-else-if="mode === 'cloze'">
          <small class="muted">Completa con la palabra que falta:</small>
          <div class="big-text">{{ clozeText }}</div>
          <small class="muted">{{ current.extra.example_es }} · pista: {{ current.back }}</small>
        </template>
        <template v-else>
          <div class="big-text">{{ current.front }} <PlayButton :text="current.front" /></div>
          <small v-if="current.extra?.pos" class="muted">{{ current.extra.pos }}</small>
        </template>

        <div v-if="!flipped && mode !== 'recognition'" class="answer-row">
          <input type="text" v-model="typed" placeholder="Escríbelo o dilo en voz alta" />
          <RecordButton label="Decirlo" :busy="listening" :max-seconds="10" @recorded="onSpoken" />
        </div>
      </div>

      <div v-if="flipped" class="back">
        <div v-if="typedOk !== null" class="typed" :class="typedOk ? 'score-good' : 'score-bad'">
          {{ typedOk ? '✅ ¡Exacto!' : `Tú: “${typed}”` }}
        </div>
        <template v-if="mode === 'mistake'">
          <div class="big-text score-good">{{ current.back }} <PlayButton :text="current.back" /></div>
          <p class="muted">{{ current.extra?.explanation }}</p>
        </template>
        <template v-else-if="mode === 'production'">
          <div class="big-text">{{ current.front }} <PlayButton :text="current.front" /></div>
          <div v-if="current.extra?.example" class="example">{{ current.extra.example }} <PlayButton :text="current.extra.example" /></div>
          <p v-if="current.extra?.note" class="muted">💡 {{ current.extra.note }}</p>
        </template>
        <template v-else-if="mode === 'cloze'">
          <div class="big-text">{{ current.front }}</div>
          <div class="example">{{ current.extra.example }} <PlayButton :text="current.extra.example" /></div>
        </template>
        <template v-else>
          <div class="big-text">{{ current.back }}</div>
          <div v-if="current.extra?.example" class="example">
            {{ current.extra.example }} <PlayButton :text="current.extra.example" />
            <div class="muted">{{ current.extra.example_es }}</div>
          </div>
        </template>
        <div v-if="mode !== 'mistake'" class="mnemo">
          <p v-if="mnemonic">🧠 {{ mnemonic }}</p>
          <button v-else class="btn sm ghost" :disabled="mnemonicLoading" @click="getMnemonic"><span v-if="mnemonicLoading" class="spin"></span> 🧠 Truco para recordarla</button>
        </div>
      </div>

      <div class="actions">
        <button v-if="!flipped" class="btn primary lg" @click="flip">Mostrar respuesta <span class="kbd">Espacio</span></button>
        <div v-else class="rates">
          <button class="btn bad" @click="rate('again')">Otra vez <span class="kbd">1</span></button>
          <button class="btn warn" @click="rate('hard')">Difícil <span class="kbd">2</span></button>
          <button class="btn good" @click="rate('good')">Bien <span class="kbd">3</span></button>
          <button class="btn primary" @click="rate('easy')">Fácil <span class="kbd">4</span></button>
        </div>
      </div>
    </div>
    <div v-else class="card empty">
      <h2>🎉 ¡Todo repasado por hoy!</h2>
      <p>{{ done ? `Has repasado ${done} tarjetas.` : 'No hay tarjetas pendientes ahora mismo.' }}</p>
      <p class="muted">¿Quieres aprender más? Añade las siguientes palabras más frecuentes, o expresiones de los paquetes avanzados.</p>
      <div class="row" style="justify-content:center">
        <button class="btn" :disabled="adding" @click="addMore(10)">+10 palabras</button>
        <button class="btn primary" :disabled="adding" @click="addMore(20)">+20 palabras</button>
        <router-link to="/vocabulario" class="btn">📦 Paquetes y vocabulario</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.flash { max-width: 720px; margin: 0 auto; text-align: center; padding: 24px; }
.face { padding: 34px 10px 18px; }
.answer-row { display: flex; gap: 8px; max-width: 520px; margin: 16px auto 0; align-items: center; }
.answer-row input { flex: 1; }
.back { border-top: 1px dashed var(--border); padding: 20px 10px; }
.typed { font-weight: 600; margin-bottom: 8px; }
.example { margin-top: 12px; font-size: 1.05rem; }
.mnemo { margin-top: 12px; }
.mnemo p { background: var(--accent-2); padding: 8px 12px; border-radius: 10px; display: inline-block; }
.actions { margin-top: 10px; }
.rates { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
@media (max-width: 560px) { .rates { grid-template-columns: repeat(2, 1fr); } .answer-row { flex-wrap: wrap; } }
</style>
