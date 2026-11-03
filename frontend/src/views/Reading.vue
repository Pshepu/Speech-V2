<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import ClickableText from '../components/ClickableText.vue'
import PlayButton from '../components/PlayButton.vue'

const app = useApp()
const list = ref<any[]>([])
const story = ref<any>(null)
const topic = ref('')
const level = ref(app.level)
const generating = ref(false)
const showTr = ref<Record<number, boolean>>({})
const answers = ref<Record<number, number>>({})
const finished = ref(false)

onMounted(async () => { list.value = await api.get(`/reading/list?lang=${app.lang}`) })

async function generate() {
  generating.value = true
  try {
    story.value = await api.post('/reading/generate', { lang: app.lang, level: level.value, topic: topic.value || null })
    reset()
  } catch (e: any) { app.notify(e.message, 'error') }
  generating.value = false
}
async function open(id: number) { story.value = await api.get(`/reading/${id}`); reset() }
function reset() { showTr.value = {}; answers.value = {}; finished.value = false }

async function finish() {
  const qs = story.value.questions || []
  const ok = qs.filter((q: any, i: number) => answers.value[i] === q.answer).length
  finished.value = true
  await api.post(`/reading/${story.value.id}/done`, { score: qs.length ? (100 * ok) / qs.length : 100 })
  app.notify(`Comprensión: ${ok}/${qs.length}`, 'good')
}
async function addVocab(v: any) {
  await api.post('/cards', { lang: app.lang, kind: 'phrase', front: v.t, back: v.es, source: 'reading' })
  v.added = true
}
const fullText = () => story.value.paragraphs.map((p: any) => p.t).join(' ')
</script>

<template>
  <div>
    <div class="page-head">
      <div><h1>📖 Lectura y escucha</h1><p>Input comprensible: historias a tu nivel con audio. Toca cualquier palabra para traducirla y guardarla.</p></div>
    </div>

    <div v-if="!story">
      <div class="card">
        <h3>Generar una historia nueva</h3>
        <div class="row">
          <input type="text" v-model="topic" placeholder="Tema (opcional): misterio, viaje a Japón, fútbol, tecnología…" style="flex:1" />
          <select v-model="level" style="width:auto"><option v-for="l in app.meta.levels" :key="l">{{ l }}</option></select>
          <button class="btn primary" :disabled="generating" @click="generate"><span v-if="generating" class="spin"></span> Generar</button>
        </div>
      </div>
      <div class="card" v-if="list.length">
        <h3>Tus lecturas</h3>
        <button v-for="r in list" :key="r.id" class="item" @click="open(r.id)">
          <span>{{ r.read_done ? '✅' : '📄' }} {{ r.title }}</span><span class="chip">{{ r.level }}</span>
        </button>
      </div>
    </div>

    <div v-else>
      <button class="btn sm ghost" @click="story = null">← Lecturas</button>
      <div class="card reader" style="margin-top:8px">
        <div class="row between">
          <div><h2 style="margin:0">{{ story.title }}</h2><small class="muted">{{ story.title_es }} · {{ story.level }}</small></div>
          <div class="row"><PlayButton :text="fullText()" label="Escuchar todo" size="" /><PlayButton :text="fullText()" :rate="-25" label="Lento" size="" /></div>
        </div>
        <div v-for="(p, i) in story.paragraphs" :key="i" class="para">
          <p class="text"><ClickableText :text="p.t" /></p>
          <div class="row">
            <PlayButton :text="p.t" />
            <button class="btn sm ghost" @click="showTr[i] = !showTr[i]">🇪🇸 {{ showTr[i] ? 'Ocultar' : 'Traducir' }}</button>
          </div>
          <p v-if="showTr[i]" class="muted">{{ p.es }}</p>
        </div>
      </div>

      <div class="card" v-if="story.vocab?.length">
        <h3>Vocabulario clave</h3>
        <div v-for="v in story.vocab" :key="v.t" class="row between vrow">
          <span><b>{{ v.t }}</b> — {{ v.es }}</span>
          <div class="row"><PlayButton :text="v.t" /><button class="btn sm" :disabled="v.added" @click="addVocab(v)">{{ v.added ? '✓' : '+ Repaso' }}</button></div>
        </div>
      </div>

      <div class="card" v-if="story.questions?.length">
        <h3>Comprensión</h3>
        <div v-for="(q, i) in story.questions" :key="i" style="margin-bottom:14px">
          <b>{{ i + 1 }}. {{ q.q }}</b>
          <div class="row" style="margin-top:6px">
            <button v-for="(o, k) in q.options" :key="k" class="chip"
                    :class="finished ? (k === q.answer ? 'good' : answers[i] === k ? 'bad' : '') : answers[i] === k ? 'on' : ''"
                    :disabled="finished" @click="answers[i] = k">{{ o }}</button>
          </div>
        </div>
        <button class="btn primary" :disabled="finished || Object.keys(answers).length < story.questions.length" @click="finish">Comprobar y terminar</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.item { display: flex; justify-content: space-between; width: 100%; font: inherit; color: var(--text); background: none; border: none; border-bottom: 1px solid var(--border); padding: 10px 4px; cursor: pointer; text-align: left; }
.item:hover { background: var(--surface-2); }
.reader .para { margin-top: 18px; }
.reader .text { font-size: 1.18rem; line-height: 1.75; margin-bottom: 4px; }
.vrow { padding: 6px 0; border-bottom: 1px solid var(--border); }
</style>
