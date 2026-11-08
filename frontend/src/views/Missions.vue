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
const unfinished = ref<any[]>([])
const budget = ref<any>(null)
const engine = ref('scene')
const pendingFor = (id: string) => unfinished.value.find((u) => u.mission_id === id)
function resume(u: any) { router.push(`/mision/${u.run_id}`) }
async function discard(u: any) {
  await api.del(`/runs/${u.run_id}`)
  unfinished.value = unfinished.value.filter((x) => x.run_id !== u.run_id)
}
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
  unfinished.value = await api.get(`/runs/unfinished?lang=${app.lang}`)
  budget.value = await api.get('/budget')
}

onMounted(async () => {
  await load()
  const s = route.query.start as string
  if (s) open(s)
})

async function open(id: string) {
  notes.value = ''; planning.value = 0
  briefing.value = await api.get(`/missions/${id}?lang=${app.lang}`)
}

const info = (id: string) => campaigns.value.flatMap((c) => c.missions).find((m: any) => m.id === id)
// Pre-tarea: 1 minuto de planificación antes de hablar mejora fluidez y complejidad.
const planning = ref(0)
const notes = ref('')
let planTimer: any = null
function startPlanning() {
  planning.value = 60
  clearInterval(planTimer)
  planTimer = setInterval(() => { planning.value--; if (planning.value <= 0) clearInterval(planTimer) }, 1000)
}

async function start(repeat = false) {
  starting.value = true
  clearInterval(planTimer); planning.value = 0
  const old = pendingFor(briefing.value.id)
  if (old) await api.del(`/runs/${old.run_id}`)  // empezar de nuevo descarta la partida anterior
  try {
    if (notes.value.trim()) sessionStorage.setItem(`notes-${briefing.value.id}`, notes.value)
    const r = await api.post(`/missions/${briefing.value.id}/start`, { lang: app.lang, mode: mode.value, repeat, engine: engine.value })
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

const dailyLoading = ref(false)
async function openDaily() {
  dailyLoading.value = true
  try { briefing.value = await api.get(`/missions/daily?lang=${app.lang}`); load() }
  catch (e: any) { app.notify(e.message, 'error') }
  dailyLoading.value = false
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
      <div v-if="budget" class="budget" title="Cuota gratuita diaria de Groq (se recupera durante el día)">
        ⚡ IA hoy: ≈ <b>{{ budget.missions_left_saver }}</b> misiones en modo ahorro · {{ budget.missions_left }} con IA en cada turno
      </div>
    </div>

    <div v-if="unfinished.length" class="card resume">
      <h3>▶️ Continuar donde lo dejaste</h3>
      <div v-for="u in unfinished" :key="u.run_id" class="row between urow">
        <span><b>{{ u.title }}</b> <small class="muted">· {{ u.character }} · {{ u.free ? `${u.turns} turnos` : `${u.done}/${u.objectives} objetivos` }} · {{ new Date(u.started).toLocaleDateString() }}</small></span>
        <div class="row"><button class="btn sm primary" @click="resume(u)">Continuar</button><button class="btn sm ghost" title="Descartar" @click="discard(u)">✕</button></div>
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

    <div class="card daily">
      <div class="row between">
        <div><h3 style="margin:0">🌅 Misión del día</h3><small class="muted">Una misión nueva cada día, a tu nivel y conectada con tu vida. Nunca te quedarás sin práctica.</small></div>
        <button class="btn mission" :disabled="dailyLoading" @click="openDaily"><span v-if="dailyLoading" class="spin"></span> Ver misión de hoy</button>
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
            <span v-if="m.repeat_due" class="chip mission" style="align-self:flex-start;margin-top:4px">🔁 Repetir y mejorar tu marca</span>
          </div>
        </button>
      </div>
    </div>

    <div v-if="runs.length" class="card">
      <h3>Historial</h3>
      <div v-for="r in runs" :key="r.id" class="row between hist">
        <span>{{ r.abandoned ? '🗑️' : r.success ? '✅' : '⏹️' }} {{ titleOf(r.mission_id) }} <small class="muted">· {{ r.mode }}</small></span>
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
        <div class="prep">
          <div class="row between">
            <b>🧠 Prepárate (opcional, 1 minuto)</b>
            <button v-if="!planning" class="btn sm" @click="startPlanning">⏱️ Empezar</button>
            <span v-else class="chip on">⏱️ {{ planning }} s</span>
          </div>
          <small class="muted">Planificar un minuto antes de hablar mejora tu fluidez. Piensa qué vas a decir para cada objetivo.</small>
          <template v-if="planning || notes">
            <div v-if="briefing.useful_phrases?.length" class="phr">
              <div v-for="p in briefing.useful_phrases" :key="p.t"><b>{{ p.t }}</b> <small class="muted">— {{ p.es }}</small></div>
            </div>
            <textarea v-model="notes" rows="3" placeholder="Tus notas: palabras clave, frases que quieres usar…"></textarea>
          </template>
        </div>
        <h3>Motor</h3>
        <div class="modes" style="margin-bottom:10px">
          <button class="mode" :class="{ on: engine === 'scene' }" @click="engine = 'scene'">
            <b>⚡ Modo ahorro (recomendado)</b><small>Escena preparada: la mayoría de respuestas no gastan cuota de IA. Correcciones en el informe final. La primera vez tarda unos segundos en prepararse.</small></button>
          <button class="mode" :class="{ on: engine === 'llm' }" @click="engine = 'llm'">
            <b>🤖 IA en cada turno</b><small>Más flexible y con corrección al momento, pero gasta mucha más cuota diaria.</small></button>
        </div>
        <h3>Modo</h3>
        <div class="modes">
          <button class="mode" :class="{ on: mode === 'entrenamiento' }" @click="mode = 'entrenamiento'">
            <b>🛡️ Entrenamiento</b><small>Pistas, traducciones, frases útiles y correcciones al momento.</small></button>
          <button class="mode" :class="{ on: mode === 'inmersion' }" @click="mode = 'inmersion'">
            <b>🔥 Inmersión total</b><small>Sin ayudas. Las correcciones solo se ven en el informe final.</small></button>
        </div>
        <div class="row" style="margin-top:18px">
          <button class="btn" @click="briefing = null">Cancelar</button>
          <button v-if="pendingFor(briefing.id)" class="btn primary lg" @click="resume(pendingFor(briefing.id))">▶️ Continuar ({{ pendingFor(briefing.id).done }}/{{ pendingFor(briefing.id).objectives }})</button>
          <button class="btn mission lg" :disabled="starting" @click="start(false)"><span v-if="starting" class="spin"></span> {{ pendingFor(briefing.id) ? 'Empezar de nuevo' : 'Iniciar misión' }}</button>
          <button v-if="info(briefing.id)?.completed" class="btn lg" :disabled="starting" title="Misma misión con otros nombres, cifras e imprevisto" @click="start(true)">🔁 Repetir con variación</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.campaign { margin-bottom: 16px; }
.budget { background: var(--surface-2); padding: 6px 12px; border-radius: 10px; font-size: .9rem; }
.prep { background: var(--surface-2); border-radius: 12px; padding: 12px; margin: 10px 0; display: flex; flex-direction: column; gap: 6px; }
.phr { font-size: .92rem; }
.daily { margin-bottom: 16px; border-left: 4px solid var(--mission); }
.missions { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
.mission-card { display: flex; gap: 12px; text-align: left; font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px; cursor: pointer; }
.mission-card:hover:not(:disabled) { border-color: var(--mission); background: var(--mission-2); }
.mission-card.locked { opacity: .5; cursor: not-allowed; }
.mission-card.done .num { background: var(--good-2); color: var(--good); }
.mission-card .num { flex: none; width: 34px; height: 34px; border-radius: 50%; background: var(--mission-2); color: var(--mission); display: grid; place-items: center; font-weight: 750; }
.mission-card .info { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.resume { margin-bottom: 16px; border-color: var(--accent); }
.urow { padding: 6px 0; border-bottom: 1px solid var(--border); }
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
