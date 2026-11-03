<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'

const app = useApp()
const plan = ref<any>(null)

onMounted(async () => { plan.value = await api.get(`/plan?lang=${app.lang}`) })

const greeting = computed(() => {
  const h = new Date().getHours()
  return h < 12 ? 'Buenos días' : h < 20 ? 'Buenas tardes' : 'Buenas noches'
})
const pct = computed(() => plan.value ? Math.min(100, (100 * plan.value.minutes_today) / plan.value.goal_minutes) : 0)
const icons: Record<string, string> = { srs: '🧠', pronunciation: '🎙️', listening: '👂', grammar: '📐', mission: '🕹️', input: '📖', fluency: '⚡', assessment: '🎯' }
</script>

<template>
  <div v-if="plan">
    <div class="page-head">
      <div>
        <h1>{{ greeting }} 👋</h1>
        <p>{{ app.langInfo?.flag }} {{ app.langInfo?.name }} · nivel {{ app.level }} — tu entrenamiento de hoy</p>
      </div>
      <router-link to="/metodo" class="btn sm">🧭 ¿Por qué este plan?</router-link>
    </div>

    <div class="grid stats-row" style="margin-bottom:16px">
      <div class="card stat">
        <div class="big">🔥 {{ plan.streak.current }}</div>
        <small>días de racha · récord {{ plan.streak.best }}</small>
      </div>
      <div class="card stat">
        <div class="big">⭐ {{ plan.xp_today }}</div>
        <small>XP hoy</small>
      </div>
      <div class="card stat">
        <div class="row between"><div class="big">⏱️ {{ Math.round(plan.minutes_today) }}<small>/{{ plan.goal_minutes }} min</small></div></div>
        <div class="progress"><div :style="{ width: pct + '%' }"></div></div>
      </div>
    </div>

    <div class="card">
      <div class="row between" style="margin-bottom:12px">
        <h2 style="margin:0">Plan de hoy</h2>
        <span class="chip" :class="plan.done === plan.tasks.length ? 'good' : ''">{{ plan.done }}/{{ plan.tasks.length }} completadas</span>
      </div>
      <div class="tasks">
        <router-link v-for="t in plan.tasks" :key="t.id" :to="t.route" class="task" :class="{ done: t.done, mission: t.id === 'mission' }">
          <div class="ic">{{ t.done ? '✅' : icons[t.id] }}</div>
          <div class="body">
            <div class="row between"><b>{{ t.title }}</b><small class="muted">~{{ t.minutes }} min <span v-if="t.progress">· {{ t.progress }}</span></small></div>
            <div>{{ t.detail }}</div>
            <small class="muted">{{ t.why }}</small>
          </div>
          <div class="go">›</div>
        </router-link>
      </div>
    </div>

    <div class="grid two" style="margin-top:16px">
      <router-link to="/misiones" class="card cta mission">
        <h3>🎯 Misiones de inmersión</h3>
        <p class="muted">Habla con personajes en situaciones reales para conseguir lo que necesitas. Como el entrenamiento militar de idiomas.</p>
      </router-link>
      <router-link to="/repaso" class="card cta">
        <h3>🧠 Repaso · {{ plan.srs.due }} pendientes</h3>
        <p class="muted">{{ plan.srs.total }} tarjetas en tu mazo · {{ plan.srs.new_left_today }} nuevas disponibles hoy</p>
      </router-link>
    </div>

    <div v-if="!app.aiReady" class="card" style="margin-top:16px;border-color:var(--warn)">
      ⚠️ Falta la clave de IA (<code>GROQ_API_KEY</code> en el archivo <code>.env</code>). Sin ella no funcionan misiones, conversación, lecturas ni la corrección con IA.
    </div>
  </div>
  <div v-else class="empty"><span class="spin"></span></div>
</template>

<style scoped>
.stats-row { grid-template-columns: repeat(3, 1fr); }
@media (max-width: 600px) {
  .stats-row { gap: 8px; }
  .stats-row .card { padding: 12px; }
  .stat .big { font-size: 1.2rem !important; }
}
.stat .big { font-size: 1.6rem; font-weight: 750; }
.stat .big small { font-size: .9rem; color: var(--muted); font-weight: 500; }
.stat .progress { margin-top: 8px; }
.tasks { display: flex; flex-direction: column; gap: 8px; }
.task { display: flex; gap: 14px; align-items: center; padding: 12px 14px; border: 1px solid var(--border); border-radius: 12px; color: var(--text); transition: border-color .15s, background .15s; }
.task:hover { border-color: var(--accent); background: var(--accent-2); }
.task.mission { border-left: 4px solid var(--mission); }
.task.done { opacity: .6; }
.task .ic { font-size: 1.5rem; width: 36px; text-align: center; }
.task .body { flex: 1; min-width: 0; }
.task .go { font-size: 1.6rem; color: var(--muted); }
.cta { display: block; color: var(--text); }
.cta:hover { border-color: var(--accent); }
.cta.mission:hover { border-color: var(--mission); }
</style>
