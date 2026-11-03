<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import { speak } from '../composables/audio'
import PlayButton from '../components/PlayButton.vue'

const app = useApp()
const queue = ref<any[]>([])
const info = ref<any>(null)
const flipped = ref(false)
const done = ref(0)
const loading = ref(true)
const started = ref(Date.now())
const typed = ref('')
const adding = ref(false)

async function load() {
  loading.value = true
  info.value = await api.get(`/srs/queue?lang=${app.lang}`)
  queue.value = info.value.cards
  loading.value = false
  started.value = Date.now()
  if (current.value) autoplay()
}
onMounted(() => { load(); window.addEventListener('keydown', onKey) })
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

const current = computed(() => queue.value[0])
// Las frases se estudian en dirección de PRODUCCIÓN (español → idioma meta): más difícil y más útil.
const production = computed(() => current.value?.kind === 'phrase' || current.value?.kind === 'sentence')

function autoplay() {
  const c = current.value
  if (c && c.kind === 'word') speak(c.front)
}

function flip() {
  flipped.value = true
  const c = current.value
  if (production.value || c.kind === 'mistake') speak(c.kind === 'mistake' ? c.back : c.front)
}

async function rate(r: string) {
  const c = current.value
  if (!c) return
  const seconds = (Date.now() - started.value) / 1000
  queue.value.shift()
  flipped.value = false
  typed.value = ''
  done.value++
  // "Otra vez" la vuelve a mostrar en esta misma sesión (paso de aprendizaje).
  if (r === 'again') queue.value.splice(Math.min(4, queue.value.length), 0, c)
  api.post('/srs/review', { card_id: c.id, rating: r, seconds }).catch(() => {})
  started.value = Date.now()
  if (current.value) autoplay()
}

async function addMore(n: number) {
  adding.value = true
  const r = await api.post('/cards/bulk', { lang: app.lang, count: n })
  app.notify(`${r.added} palabras nuevas añadidas`, 'good')
  adding.value = false
  load()
}

async function suspend() {
  const c = current.value
  await api.del(`/cards/${c.id}`)
  queue.value.shift(); flipped.value = false
}

function onKey(e: KeyboardEvent) {
  if ((e.target as HTMLElement)?.tagName === 'INPUT') { if (e.key === 'Enter' && !flipped.value) flip(); return }
  if (!current.value) return
  if (!flipped.value && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); flip() }
  else if (flipped.value) {
    const map: any = { '1': 'again', '2': 'hard', '3': 'good', '4': 'easy', ' ': 'good' }
    if (map[e.key]) { e.preventDefault(); rate(map[e.key]) }
  }
}
const KIND: Record<string, string> = { word: 'Palabra', phrase: 'Frase', sentence: 'Frase', mistake: 'Tu error' }
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
        <span class="chip" :class="current.kind === 'mistake' ? 'bad' : 'on'">{{ KIND[current.kind] }}</span>
        <div class="row"><small class="muted">{{ done }} repasadas · {{ queue.length }} quedan</small>
          <button class="btn sm ghost" title="No volver a mostrar" @click="suspend">🗑️</button></div>
      </div>

      <div class="face">
        <template v-if="current.kind === 'mistake'">
          <small class="muted">¿Cómo se dice correctamente?</small>
          <div class="big-text"><s class="muted">{{ current.front }}</s></div>
        </template>
        <template v-else-if="production">
          <small class="muted">Dilo en {{ app.langInfo.name.toLowerCase() }}:</small>
          <div class="big-text">🇪🇸 {{ current.back }}</div>
          <input v-if="!flipped" type="text" v-model="typed" placeholder="Escríbelo o dilo en voz alta (opcional)" style="max-width:480px;margin:14px auto 0" />
        </template>
        <template v-else>
          <div class="big-text">{{ current.front }} <PlayButton :text="current.front" /></div>
          <small v-if="current.extra?.pos" class="muted">{{ current.extra.pos }}</small>
        </template>
      </div>

      <div v-if="flipped" class="back">
        <template v-if="current.kind === 'mistake'">
          <div class="big-text score-good">{{ current.back }} <PlayButton :text="current.back" /></div>
          <p class="muted">{{ current.extra?.explanation }}</p>
        </template>
        <template v-else-if="production">
          <div class="big-text">{{ current.front }} <PlayButton :text="current.front" /></div>
          <p v-if="typed" class="muted">Tú: {{ typed }}</p>
        </template>
        <template v-else>
          <div class="big-text">{{ current.back }}</div>
          <div v-if="current.extra?.example" class="example">
            {{ current.extra.example }} <PlayButton :text="current.extra.example" />
            <div class="muted">{{ current.extra.example_es }}</div>
          </div>
        </template>
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
      <p class="muted">¿Quieres aprender más? Añade las siguientes palabras más frecuentes del idioma (las que más rentan).</p>
      <div class="row" style="justify-content:center">
        <button class="btn" :disabled="adding" @click="addMore(10)">+10 palabras</button>
        <button class="btn primary" :disabled="adding" @click="addMore(20)">+20 palabras</button>
        <router-link to="/vocabulario" class="btn">Elegir del vocabulario</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.flash { max-width: 720px; margin: 0 auto; text-align: center; padding: 24px; }
.face { padding: 40px 10px 20px; }
.back { border-top: 1px dashed var(--border); padding: 20px 10px; }
.example { margin-top: 12px; font-size: 1.05rem; }
.actions { margin-top: 10px; }
.rates { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
@media (max-width: 560px) { .rates { grid-template-columns: repeat(2, 1fr); } }
</style>
