<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useApp } from '../store'

const app = useApp()
const route = useRoute()
const router = useRouter()
const campaigns = ref<any[]>([])
const briefing = ref<any>(null)
const mode = ref('entrenamiento')
const starting = ref(false)
const genTheme = ref('')
const generating = ref(false)
const freeTopic = ref('')
const runs = ref<any[]>([])
const modes = ref<any[]>([])
const kind = ref('libre')
const TOPIC_HINT: Record<string, string> = {
  libre: 'Tema (opcional): fútbol, mi trabajo, viajes…',
  debate: 'Tema del debate: ¿teletrabajo sí o no?, redes sociales…',
  entrevista: 'Puesto: desarrollador, enfermera, camarero…',
  explicar: '¿Qué vas a explicar? Tu trabajo, un deporte, una receta…',
  historia: 'Tema: un viaje, un susto, la mejor fiesta…',
  actualidad: 'Tema: inteligencia artificial, cambio climático…',
  smalltalk: 'Contexto: fiesta, oficina, avión…',
}

async function load() {
  if (!modes.value.length) modes.value = await api.get('/conversation/modes')
  campaigns.value = await api.get(`/missions?lang=${app.lang}`)
  runs.value = await api.get(`/runs?lang=${app.lang}`)
}

onMounted(async () => {
  await load()
  const s = route.query.start as string
  if (s) open(s)
})

async function open(id: string) {
  briefing.value = await api.get(`/missions/${id}?lang=${app.lang}`)
}

async function start() {
  starting.value = true
  try {
    const r = await api.post(`/missions/${briefing.value.id}/start`, { lang: app.lang, mode: mode.value })
    sessionStorage.setItem(`run-${r.run_id}`, JSON.stringify(r))
    router.push(`/mision/${r.run_id}`)
  } catch (e: any) { app.notify(e.message, 'error') }
  starting.value = false
}

async function startFree() {
  starting.value = true
  try {
    const r = await api.post('/conversation/start', { lang: app.lang, kind: kind.value, topic: freeTopic.value || 'anything interesting: daily life, hobbies, travel, work', mode: mode.value })
    sessionStorage.setItem(`run-${r.run_id}`, JSON.stringify(r))
    router.push(`/mision/${r.run_id}`)
  } catch (e: any) { app.notify(e.message, 'error') }
  starting.value = false
}

async function generate() {
  generating.value = true
  try {
    const m = await api.post('/missions/generate', { lang: app.lang, theme: genTheme.value || null })
    await load()
    briefing.value = m
  } catch (e: any) { app.notify(e.message, 'error') }
  generating.value = false
}
const titleOf = (id: string) => campaigns.value.flatMap((c) => c.missions).find((m: any) => m.id === id)?.title || 'Conversación libre'
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>🎯 Misiones</h1>
        <p>Aprende como en el entrenamiento militar de idiomas: recibes un informe, cumples la operación hablando solo en el idioma y al final analizas tus errores.</p>
      </div>
    </div>

    <div class="grid two" style="margin-bottom:20px">
      <div class="card">
        <h3>💬 Conversación con tutor</h3>
        <div class="row" style="margin-bottom:10px">
          <button v-for="m in modes" :key="m.id" class="chip" :class="{ on: kind === m.id }" :title="m.desc" @click="kind = m.id">{{ m.icon }} {{ m.title }}</button>
        </div>
        <p class="muted" style="margin-bottom:8px">{{ modes.find((m) => m.id === kind)?.desc }}</p>
        <div class="row"><input type="text" v-model="freeTopic" :placeholder="TOPIC_HINT[kind]" style="flex:1" @keydown.enter="startFree" />
          <button class="btn primary" :disabled="starting" @click="startFree"><span v-if="starting" class="spin"></span> Empezar</button></div>
      </div>
      <div class="card mission">
        <h3>🎲 Misión generada por IA</h3>
        <p class="muted">Una misión nueva a tu nivel ({{ app.level }}), sobre el tema que quieras.</p>
        <div class="row"><input type="text" v-model="genTheme" placeholder="Tema (opcional): aeropuerto, banco, cita médica…" style="flex:1" />
          <button class="btn mission" :disabled="generating" @click="generate"><span v-if="generating" class="spin"></span> Generar</button></div>
      </div>
    </div>

    <div v-for="c in campaigns" :key="c.id" class="card campaign">
      <h2>{{ c.title }}</h2>
      <p class="muted">{{ c.description }}</p>
      <div class="missions">
        <button v-for="(m, k) in c.missions" :key="m.id" class="mission-card" :class="{ locked: !m.unlocked, done: m.completed }"
                :disabled="!m.unlocked" @click="open(m.id)">
          <div class="num">{{ m.completed ? '✓' : m.unlocked ? k + 1 : '🔒' }}</div>
          <div class="info">
            <div class="row between"><b>{{ m.title }}</b><span class="chip">{{ m.level }}</span></div>
            <small class="muted">{{ m.location }}</small>
            <small>👤 {{ m.character }} <span v-if="m.best_score != null" class="muted">· mejor: {{ Math.round(m.best_score) }}</span></small>
          </div>
        </button>
      </div>
    </div>

    <div v-if="runs.length" class="card">
      <h3>Historial</h3>
      <div v-for="r in runs" :key="r.id" class="row between hist">
        <span>{{ r.success ? '✅' : '⏹️' }} {{ titleOf(r.mission_id) }} <small class="muted">· {{ r.mode }}</small></span>
        <small class="muted">{{ r.score != null ? Math.round(r.score) + ' pts · ' : '' }}{{ new Date(r.started).toLocaleDateString() }}</small>
      </div>
    </div>

    <div v-if="briefing" class="overlay" @click.self="briefing = null">
      <div class="card brief">
        <div class="tag">INFORME DE MISIÓN · {{ briefing.level }}</div>
        <h2>{{ briefing.title }}</h2>
        <p class="muted">📍 {{ briefing.location }}</p>
        <p>{{ briefing.briefing }}</p>
        <p>👤 Contacto: <b>{{ briefing.character.name }}</b> <small class="muted">({{ briefing.character.role }})</small></p>
        <h3>Objetivos</h3>
        <ul class="objs"><li v-for="o in briefing.objectives" :key="o.id">☐ {{ o.text }}</li></ul>
        <h3>Modo</h3>
        <div class="modes">
          <button class="mode" :class="{ on: mode === 'entrenamiento' }" @click="mode = 'entrenamiento'">
            <b>🛡️ Entrenamiento</b><small>Pistas, traducciones, frases útiles y correcciones al momento.</small></button>
          <button class="mode" :class="{ on: mode === 'inmersion' }" @click="mode = 'inmersion'">
            <b>🔥 Inmersión total</b><small>Sin ayudas. Las correcciones solo se ven en el informe final.</small></button>
        </div>
        <div class="row" style="margin-top:18px">
          <button class="btn" @click="briefing = null">Cancelar</button>
          <button class="btn mission lg" :disabled="starting" @click="start"><span v-if="starting" class="spin"></span> Iniciar misión</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.campaign { margin-bottom: 16px; }
.missions { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
.mission-card { display: flex; gap: 12px; text-align: left; font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px; cursor: pointer; }
.mission-card:hover:not(:disabled) { border-color: var(--mission); background: var(--mission-2); }
.mission-card.locked { opacity: .5; cursor: not-allowed; }
.mission-card.done .num { background: var(--good-2); color: var(--good); }
.mission-card .num { flex: none; width: 34px; height: 34px; border-radius: 50%; background: var(--mission-2); color: var(--mission); display: grid; place-items: center; font-weight: 750; }
.mission-card .info { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.hist { padding: 6px 0; border-bottom: 1px solid var(--border); }
.overlay { position: fixed; inset: 0; background: rgba(10, 12, 20, .55); z-index: 50; display: grid; place-items: center; padding: 16px; }
.brief { max-width: 620px; width: 100%; max-height: 92vh; overflow-y: auto; border-top: 5px solid var(--mission); }
.tag { font-family: var(--mono); font-size: .75rem; letter-spacing: .12em; color: var(--mission); margin-bottom: 6px; }
.objs { list-style: none; padding: 0; }
.objs li { padding: 3px 0; }
.modes { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
@media (max-width: 560px) { .modes { grid-template-columns: 1fr; } }
.mode { text-align: left; font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px; cursor: pointer; display: flex; flex-direction: column; gap: 4px; }
.mode.on { border-color: var(--mission); background: var(--mission-2); }
</style>
