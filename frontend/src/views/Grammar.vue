<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'

const app = useApp()
const lessons = ref<any[]>([])
const mistakes = ref<any[]>([])
onMounted(async () => {
  lessons.value = await api.get(`/grammar?lang=${app.lang}`)
  mistakes.value = await api.get(`/mistakes?lang=${app.lang}&limit=30`)
})
const byLevel = computed(() => {
  const g: Record<string, any[]> = {}
  for (const l of lessons.value) (g[l.level] ??= []).push(l)
  return Object.entries(g)
})
</script>

<template>
  <div>
    <div class="page-head">
      <div><h1>📐 Gramática</h1><p>Explicaciones cortas en español, pensadas para hispanohablantes, y práctica inmediata. Tus errores se convierten en tarjetas de repaso.</p></div>
      <router-link to="/escritura" class="btn">✍️ Escritura libre con corrección</router-link>
    </div>
    <div v-if="!lessons.length" class="card empty">Las lecciones aún se están generando. Ejecuta <code>python scripts/build_content.py</code> si no aparecen.</div>
    <div v-for="[lvl, ls] in byLevel" :key="lvl" class="card">
      <h2>Nivel {{ lvl }}</h2>
      <div class="lessons">
        <router-link v-for="l in ls" :key="l.id" :to="`/gramatica/${l.id}`" class="lesson" :class="{ done: l.completed }">
          <div class="row between"><b>{{ l.completed ? '✅ ' : '' }}{{ l.title }}</b><small v-if="l.best_score != null" class="muted">{{ Math.round(l.best_score) }}%</small></div>
          <small class="muted">{{ l.summary }}</small>
        </router-link>
      </div>
    </div>
    <div v-if="mistakes.length" class="card">
      <h2>📓 Tu cuaderno de errores</h2>
      <p class="muted">Errores detectados en misiones, conversación, escritura y ejercicios. Todos están en tu repaso.</p>
      <div v-for="m in mistakes" :key="m.id" class="mrow">
        <s class="muted">{{ m.original }}</s> → <b>{{ m.corrected }}</b>
        <div><small>{{ m.explanation }}</small> <span class="chip">{{ m.category }}</span> <span class="chip">{{ m.source }}</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lessons { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
.lesson { display: block; padding: 12px 14px; border: 1px solid var(--border); border-radius: 12px; color: var(--text); }
.lesson:hover { border-color: var(--accent); background: var(--accent-2); }
.lesson.done { background: var(--good-2); border-color: transparent; }
.mrow { padding: 8px 0; border-bottom: 1px solid var(--border); }
</style>
