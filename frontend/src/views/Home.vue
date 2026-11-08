<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'

const app = useApp()
const plan = ref<any>(null)
const journey = ref<any>(null)
const unfinished = ref<any[]>([])
const showExtra = ref(false)

onMounted(async () => {
  const [p, j, u] = await Promise.all([
    api.get(`/plan?lang=${app.lang}`), api.get(`/journey?lang=${app.lang}`), api.get(`/runs/unfinished?lang=${app.lang}`),
  ])
  plan.value = p; journey.value = j; unfinished.value = u
})

const greeting = computed(() => {
  const h = new Date().getHours()
  return h < 12 ? 'Buenos días' : h < 20 ? 'Buenas tardes' : 'Buenas noches'
})
const minPct = computed(() => plan.value ? Math.min(100, (100 * plan.value.minutes_today) / plan.value.goal_minutes) : 0)
const core = computed(() => plan.value?.tasks.filter((t: any) => t.core) || [])
const extra = computed(() => plan.value?.tasks.filter((t: any) => !t.core) || [])
const icons: Record<string, string> = { srs: '🧠', pronunciation: '🎙️', listening: '👂', grammar: '📐', mission: '🕹️', input: '📖', fluency: '⚡', assessment: '🎯' }
const DAYS = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
const weekMinutes = computed(() => journey.value ? journey.value.weeks[journey.value.weeks.length - 1].minutes : 0)
const lastWeekMinutes = computed(() => journey.value ? journey.value.weeks[journey.value.weeks.length - 2].minutes : 0)
const fmtDate = (d: string) => new Date(d + 'T12:00:00').toLocaleDateString('es-CL', { day: 'numeric', month: 'long' })

// Comparación "cuando empezaste" vs "ahora"
const compare = computed(() => {
  if (!journey.value) return []
  const b = journey.value.baseline, n = journey.value.now
  const rows = [
    { label: 'Palabras dominadas', from: b.words_known, to: n.words_known },
    { label: 'Misiones completadas', from: b.missions_done, to: n.missions_done },
    { label: 'Lecciones de gramática', from: b.lessons_done, to: n.lessons_done },
    { label: 'Horas de práctica', from: Math.round(b.total_minutes / 6) / 10, to: Math.round(n.total_minutes / 6) / 10 },
  ]
  if (b.pronunciation || n.pronunciation) rows.push({ label: 'Pronunciación media', from: b.pronunciation ?? '—', to: n.pronunciation ?? '—' })
  if (b.vocab_size || n.vocab_size) rows.push({ label: 'Tamaño de vocabulario (test)', from: b.vocab_size ?? '—', to: n.vocab_size ?? '—' })
  return rows
})
// Si una destreza medida está muy por encima del nivel configurado, el contenido será demasiado fácil.
const LV = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
const levelHint = computed(() => {
  if (!journey.value) return null
  const sk = journey.value.now.skills || {}
  const measured = Object.entries(sk).filter(([, v]) => v && LV.includes(v as string)) as [string, string][]
  const best = measured.sort((a, b) => LV.indexOf(b[1]) - LV.indexOf(a[1]))[0]
  if (!best) return null
  const gap = LV.indexOf(best[1]) - LV.indexOf(app.level)
  const names: Record<string, string> = { vocabulary: 'vocabulario', speaking: 'expresión oral', writing: 'escritura', listening: 'comprensión auditiva', reading: 'lectura' }
  return gap >= 2 ? { skill: names[best[0]] || best[0], level: best[1] } : null
})
const measuredSkills = computed(() => Object.entries(journey.value?.now.skills || {}).filter(([, v]) => v))
const delta = (r: any) => (typeof r.from === 'number' && typeof r.to === 'number' ? Math.round((r.to - r.from) * 10) / 10 : null)
</script>

<template>
  <div v-if="plan && journey">
    <div class="page-head">
      <div>
        <h1>{{ greeting }} 👋</h1>
        <p>{{ app.langInfo?.flag }} {{ app.langInfo?.name }} · practicando desde el {{ fmtDate(journey.baseline.date) }}</p>
      </div>
      <router-link to="/metodo" class="btn sm">🧭 ¿Por qué este plan?</router-link>
    </div>

    <!-- 1. HOY: lo esencial, con metas claras -->
    <div class="card today" :class="{ complete: plan.day_complete }">
      <div class="row between">
        <div>
          <h2 style="margin:0">{{ plan.day_complete ? '✅ ¡Día completado!' : 'Tu objetivo de hoy' }}</h2>
          <small class="muted">El día cuenta cuando haces las <b>{{ plan.core_total }} esenciales</b> o llegas a <b>{{ plan.goal_minutes }} minutos</b>.</small>
        </div>
        <div class="minutes">
          <b>{{ Math.round(plan.minutes_today) }}</b><small>/{{ plan.goal_minutes }} min</small>
          <div class="progress"><div :style="{ width: minPct + '%' }"></div></div>
        </div>
      </div>

      <div v-if="unfinished.length" class="resume">
        ▶️ Tienes <b>{{ unfinished[0].title }}</b> a medias ({{ unfinished[0].free ? unfinished[0].turns + ' turnos' : unfinished[0].done + '/' + unfinished[0].objectives + ' objetivos' }}).
        <router-link :to="`/mision/${unfinished[0].run_id}`" class="btn sm primary">Continuar</router-link>
      </div>

      <div class="tasks">
        <router-link v-for="t in core" :key="t.id" :to="t.route" class="task" :class="{ done: t.done }">
          <div class="ic">{{ t.done ? '✅' : icons[t.id] }}</div>
          <div class="body">
            <div class="row between"><b>{{ t.title }}</b><span class="chip" :class="t.done ? 'good' : ''">{{ t.done ? 'Hecho' : t.progress }}</span></div>
            <div class="goal">🎯 {{ t.goal }}</div>
            <div class="progress thin"><div :style="{ width: (100 * t.current) / t.target + '%' }"></div></div>
            <small class="muted">{{ t.detail }}</small>
          </div>
          <div class="go">›</div>
        </router-link>
      </div>

      <button class="btn sm ghost" style="margin-top:10px" @click="showExtra = !showExtra">
        {{ showExtra ? '▴' : '▾' }} Extra opcional ({{ extra.filter((t: any) => t.done).length }}/{{ extra.length }})
      </button>
      <div v-if="showExtra" class="tasks" style="margin-top:8px">
        <router-link v-for="t in extra" :key="t.id" :to="t.route" class="task small" :class="{ done: t.done }">
          <div class="ic">{{ t.done ? '✅' : icons[t.id] }}</div>
          <div class="body">
            <div class="row between"><b>{{ t.title }}</b><span class="chip" :class="t.done ? 'good' : ''">{{ t.done ? 'Hecho' : t.goal }}</span></div>
            <small class="muted">{{ t.detail }}</small>
          </div>
          <div class="go">›</div>
        </router-link>
      </div>

      <div v-if="plan.today_log.length" class="log">
        <small class="muted"><b>Hoy ya hiciste:</b>
          <span v-for="(l, i) in plan.today_log" :key="l.kind">{{ i ? ' · ' : ' ' }}{{ l.name }} ×{{ l.n }}</span>
          · ⭐ {{ plan.xp_today }} XP</small>
      </div>
    </div>

    <!-- 2. TU SEMANA -->
    <div class="card" style="margin-top:16px">
      <div class="row between">
        <h3 style="margin:0">📅 Esta semana</h3>
        <small class="muted">🔥 racha de {{ plan.streak.current }} días · récord {{ plan.streak.best }}</small>
      </div>
      <div class="week">
        <div v-for="(d, i) in journey.this_week" :key="d.day" class="day" :class="{ future: d.future, today: d.today }">
          <div class="dot" :class="d.minutes >= journey.goal_minutes ? 'full' : d.minutes > 0 ? 'half' : ''">{{ d.minutes >= journey.goal_minutes ? '✓' : '' }}</div>
          <small>{{ DAYS[i] }}</small>
        </div>
      </div>
      <small class="muted">
        {{ weekMinutes }} min esta semana
        <template v-if="lastWeekMinutes"> · semana pasada: {{ lastWeekMinutes }} min
          <b :class="weekMinutes >= lastWeekMinutes ? 'score-good' : 'score-mid'">({{ weekMinutes >= lastWeekMinutes ? '▲' : '▼' }} {{ Math.abs(weekMinutes - lastWeekMinutes) }})</b>
        </template>
      </small>
    </div>

    <!-- 3. ¿AVANZO? Punto de partida vs ahora -->
    <div class="card" style="margin-top:16px">
      <div class="row between">
        <h3 style="margin:0">📈 ¿Estoy avanzando?</h3>
        <router-link to="/nivel" class="btn sm">Medir mi nivel</router-link>
      </div>
      <div class="road">
        <div class="lvl from"><small>Empezaste</small><b>{{ journey.baseline.level }}</b><small>{{ fmtDate(journey.baseline.date) }}</small></div>
        <div class="bar"><div class="progress"><div :style="{ width: journey.c1_progress + '%' }"></div></div>
          <small class="muted">Ahora: <b>{{ journey.current_level }}</b>{{ journey.now.overall ? ' (medido en 3+ destrezas)' : ' (configurado; mide al menos 3 destrezas para un nivel real)' }}</small>
          <small v-if="measuredSkills.length" class="muted">Medido: <span v-for="([k, v], i) in measuredSkills" :key="k">{{ i ? ' · ' : '' }}{{ ({ vocabulary: 'vocabulario', speaking: 'habla', writing: 'escritura', listening: 'escucha', reading: 'lectura' } as any)[k] }} {{ v }}</span></small></div>
        <div class="lvl to"><small>Meta</small><b>C1</b></div>
      </div>
      <div v-if="levelHint" class="hint-lvl">
        💡 Tu <b>{{ levelHint.skill }}</b> está en <b>{{ levelHint.level }}</b>, pero tu nivel configurado es <b>{{ app.level }}</b>: las misiones y frases te resultarán demasiado fáciles.
        <router-link to="/ajustes" class="btn sm">Cambiar nivel</router-link>
      </div>
      <table class="cmp">
        <thead><tr><th></th><th>Al empezar</th><th>Ahora</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in compare" :key="r.label">
            <td>{{ r.label }}</td><td class="muted">{{ r.from }}</td><td><b>{{ r.to }}</b></td>
            <td><span v-if="delta(r) !== null && delta(r) !== 0" :class="delta(r)! > 0 ? 'score-good' : 'score-bad'">{{ delta(r)! > 0 ? '+' : '' }}{{ delta(r) }}</span></td>
          </tr>
        </tbody>
      </table>
      <h4 style="margin:14px 0 8px">🏅 Próximos hitos</h4>
      <div class="ms">
        <div v-for="m in journey.milestones.filter((x: any) => !x.done).slice(0, 3)" :key="m.title" class="mrow">
          <span>{{ m.title }}</span>
          <div class="progress" style="flex:1"><div :style="{ width: (100 * m.current) / m.target + '%' }"></div></div>
          <small class="muted">{{ m.current }}/{{ m.target }}</small>
        </div>
        <small class="muted">Logrados: {{ journey.milestones.filter((x: any) => x.done).map((x: any) => x.title).join(' · ') || 'todavía ninguno — ¡a por el primero!' }}</small>
      </div>
    </div>

    <div v-if="!app.aiReady" class="card" style="margin-top:16px;border-color:var(--warn)">
      ⚠️ Falta la clave de IA (<code>GROQ_API_KEY</code> en el archivo <code>.env</code>). Sin ella no funcionan misiones, conversación, lecturas ni la corrección con IA.
    </div>
  </div>
  <div v-else class="empty"><span class="spin"></span></div>
</template>

<style scoped>
.today.complete { border-color: var(--good); }
.minutes { min-width: 130px; text-align: right; }
.minutes b { font-size: 1.6rem; }
.minutes .progress { margin-top: 4px; }
.resume { margin: 12px 0 0; padding: 10px 12px; background: var(--accent-2); border-radius: 10px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.tasks { display: flex; flex-direction: column; gap: 8px; margin-top: 14px; }
.task { display: flex; gap: 14px; align-items: center; padding: 12px 14px; border: 1px solid var(--border); border-radius: 12px; color: var(--text); }
.task:hover { border-color: var(--accent); background: var(--accent-2); }
.task.done { background: var(--good-2); border-color: transparent; }
.task.small { padding: 8px 12px; }
.task .ic { font-size: 1.5rem; width: 36px; text-align: center; }
.task .body { flex: 1; min-width: 0; }
.task .go { font-size: 1.6rem; color: var(--muted); }
.goal { font-size: .92rem; margin: 2px 0 6px; }
.progress.thin { height: 5px; margin-bottom: 4px; }
.log { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border); }
.week { display: flex; justify-content: space-between; margin: 14px 0 8px; max-width: 420px; }
.day { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.day.future { opacity: .4; }
.day.today small { font-weight: 800; color: var(--accent); }
.dot { width: 34px; height: 34px; border-radius: 50%; border: 2px solid var(--border); display: grid; place-items: center; font-weight: 800; }
.dot.half { background: var(--warn-2); border-color: var(--warn); }
.dot.full { background: var(--good); border-color: var(--good); color: #fff; }
.road { display: flex; align-items: center; gap: 12px; margin: 16px 0; }
.road .lvl { display: flex; flex-direction: column; align-items: center; min-width: 74px; }
.road .lvl b { font-size: 1.5rem; }
.road .lvl.to b { color: var(--mission); }
.road .bar { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.hint-lvl { background: var(--warn-2); padding: 10px 12px; border-radius: 10px; margin-bottom: 12px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.cmp { width: 100%; border-collapse: collapse; font-size: .93rem; }
.cmp th { text-align: left; color: var(--muted); font-weight: 600; font-size: .8rem; padding: 4px 6px; }
.cmp td { padding: 6px; border-top: 1px solid var(--border); }
.mrow { display: flex; align-items: center; gap: 10px; padding: 4px 0; }
.mrow span { width: 210px; font-size: .92rem; }
@media (max-width: 600px) { .mrow span { width: 130px; } .minutes { min-width: 90px; } }
</style>
