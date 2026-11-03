<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'

const app = useApp()
const s = ref<any>(null)
onMounted(async () => { s.value = await api.get(`/stats?lang=${app.lang}`) })

const maxXp = computed(() => Math.max(10, ...(s.value?.days || []).map((d: any) => d.xp)))
const KIND: Record<string, string> = { srs: 'Repaso', pronunciation: 'Pronunciación', listening: 'Oído', dictation: 'Dictado', grammar: 'Gramática', mission: 'Misiones', free_talk: 'Conversación', reading: 'Lectura', writing: 'Escritura', fluency: 'Fluidez' }
const totalMin = computed(() => (s.value?.by_kind || []).reduce((a: number, k: any) => a + (k.minutes || 0), 0) || 1)
</script>

<template>
  <div v-if="s">
    <div class="page-head"><div><h1>📈 Progreso</h1><p>{{ app.langInfo.flag }} {{ app.langInfo.name }}</p></div></div>
    <div class="grid three">
      <div class="card kpi"><div class="big">🔥 {{ s.streak.current }}</div><small>días seguidos (récord {{ s.streak.best }})</small></div>
      <div class="card kpi"><div class="big">⭐ {{ s.total_xp }}</div><small>XP total · {{ Math.round(s.total_minutes) }} min</small></div>
      <div class="card kpi"><div class="big">📚 {{ s.known_words }}</div><small>palabras en repaso maduro / {{ s.vocab_total }}</small></div>
      <div class="card kpi"><div class="big">🎯 {{ s.missions_done }}/{{ s.missions_total }}</div><small>misiones completadas</small></div>
      <div class="card kpi"><div class="big">📐 {{ s.lessons_done }}/{{ s.lessons_total }}</div><small>lecciones de gramática</small></div>
      <div class="card kpi"><div class="big">🧠 {{ s.srs.retention_30d != null ? Math.round(s.srs.retention_30d * 100) + '%' : '–' }}</div><small>retención en repasos (30 días)</small></div>
    </div>

    <div class="card" style="margin-top:16px">
      <h3>XP de los últimos 30 días</h3>
      <div class="chart">
        <div v-for="d in s.days" :key="d.day" class="col" :title="`${d.day}: ${d.xp} XP, ${d.minutes} min`">
          <div class="bar" :style="{ height: (100 * d.xp) / maxXp + '%' }"></div>
        </div>
      </div>
      <div class="row between"><small class="muted">{{ s.days[0].day }}</small><small class="muted">hoy</small></div>
    </div>

    <div class="grid two" style="margin-top:16px">
      <div class="card">
        <h3>Sonidos más débiles</h3>
        <div v-if="!s.weak_phonemes.length" class="muted">Practica pronunciación para ver tus sonidos débiles.</div>
        <div v-for="p in s.weak_phonemes" :key="p.phoneme" class="hrow">
          <span class="ipa" style="width:60px;font-size:1.1rem">/{{ p.phoneme }}/</span>
          <div class="progress" style="flex:1"><div :style="{ width: p.avg + '%', background: p.avg < 60 ? 'var(--bad)' : 'var(--warn)' }"></div></div>
          <small style="width:40px;text-align:right">{{ Math.round(p.avg) }}</small>
        </div>
        <router-link v-if="s.weak_phonemes.length" to="/pronunciacion" class="btn sm" style="margin-top:10px">Practicarlos →</router-link>
      </div>
      <div class="card">
        <h3>Tipos de error más frecuentes</h3>
        <div v-if="!s.mistakes_by_category.length" class="muted">Aún no hay errores registrados.</div>
        <div v-for="m in s.mistakes_by_category" :key="m.category" class="hrow">
          <span style="flex:1">{{ m.category }}</span><b>{{ m.n }}</b>
        </div>
      </div>
      <div class="card">
        <h3>Tiempo por actividad</h3>
        <div v-for="k in s.by_kind" :key="k.kind" class="hrow">
          <span style="width:120px">{{ KIND[k.kind] || k.kind }}</span>
          <div class="progress" style="flex:1"><div :style="{ width: (100 * (k.minutes || 0)) / totalMin + '%' }"></div></div>
          <small style="width:60px;text-align:right">{{ Math.round(k.minutes || 0) }} min</small>
        </div>
      </div>
      <div class="card">
        <h3>Mazo de repaso</h3>
        <div v-for="(n, k) in s.srs.by_state" :key="k" class="hrow"><span style="flex:1">{{ k }}</span><b>{{ n }}</b></div>
        <small class="muted">{{ s.srs.mature }} tarjetas maduras (estabilidad ≥ 21 días) · {{ s.srs.reviews_30d }} repasos en 30 días</small>
      </div>
      <div class="card" v-if="s.pronunciation_trend.length">
        <h3>Puntaje medio de pronunciación</h3>
        <div v-for="p in s.pronunciation_trend" :key="p.day" class="hrow">
          <small style="width:90px">{{ p.day }}</small>
          <div class="progress" style="flex:1"><div :style="{ width: p.avg + '%' }"></div></div>
          <small style="width:60px;text-align:right">{{ Math.round(p.avg) }} ({{ p.n }})</small>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="empty"><span class="spin"></span></div>
</template>

<style scoped>
.kpi .big { font-size: 1.5rem; font-weight: 750; }
.chart { display: flex; gap: 3px; align-items: flex-end; height: 140px; margin: 10px 0 6px; }
.col { flex: 1; height: 100%; display: flex; align-items: flex-end; }
.bar { width: 100%; background: var(--accent); border-radius: 4px 4px 0 0; min-height: 2px; }
.hrow { display: flex; align-items: center; gap: 10px; padding: 5px 0; }
</style>
