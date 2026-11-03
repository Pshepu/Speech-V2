<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { api } from '../api'
import { useApp } from '../store'
import PlayButton from '../components/PlayButton.vue'
import ExerciseRunner from '../components/ExerciseRunner.vue'
import ScoreRing from '../components/ScoreRing.vue'

const app = useApp()
const route = useRoute()
const lesson = ref<any>(null)
const stage = ref<'learn' | 'practice' | 'result'>('learn')
const exercises = ref<any[]>([])
const result = ref<any>(null)
const loadingMore = ref(false)
const runKey = ref(0)

onMounted(async () => {
  lesson.value = await api.get(`/grammar/${route.params.id}?lang=${app.lang}`)
  exercises.value = lesson.value.exercises
})
const html = computed(() => (lesson.value ? marked.parse(lesson.value.explanation || '') : ''))

async function onDone(r: any) {
  result.value = r
  stage.value = 'result'
  await api.post(`/grammar/${lesson.value.id}/complete`, { lang: app.lang, score: r.score, mistakes: r.mistakes })
}

async function more() {
  loadingMore.value = true
  try {
    const r = await api.post(`/grammar/${lesson.value.id}/more?lang=${app.lang}`)
    exercises.value = r.exercises
    runKey.value++
    stage.value = 'practice'
  } catch (e: any) { app.notify(e.message, 'error') }
  loadingMore.value = false
}
function retry() { exercises.value = lesson.value.exercises; runKey.value++; stage.value = 'practice' }
</script>

<template>
  <div v-if="lesson">
    <router-link to="/gramatica" class="btn sm ghost">← Gramática</router-link>
    <div class="page-head" style="margin-top:8px">
      <div><h1>{{ lesson.title }}</h1><p><span class="chip">{{ lesson.level }}</span> {{ lesson.summary }}</p></div>
    </div>

    <template v-if="stage === 'learn'">
      <div class="card markdown" v-html="html"></div>
      <div class="card" v-if="lesson.examples?.length">
        <h3>Ejemplos</h3>
        <div v-for="e in lesson.examples" :key="e.t" class="ex">
          <div class="row"><b>{{ e.t }}</b><PlayButton :text="e.t" /></div>
          <small class="muted">{{ e.es }}</small>
        </div>
      </div>
      <div class="card" v-if="lesson.common_mistakes?.length">
        <h3>⚠️ Errores típicos de hispanohablantes</h3>
        <div v-for="m in lesson.common_mistakes" :key="m.wrong" class="ex">
          <div>❌ <s class="muted">{{ m.wrong }}</s> &nbsp; ✅ <b>{{ m.right }}</b> <PlayButton :text="m.right" /></div>
          <small>{{ m.why }}</small>
        </div>
      </div>
      <div class="row" style="margin-top:16px"><button class="btn primary lg" @click="stage = 'practice'">Practicar ({{ exercises.length }} ejercicios) →</button></div>
    </template>

    <div v-else-if="stage === 'practice'" class="card" style="max-width:720px">
      <ExerciseRunner :key="runKey" :exercises="exercises" @done="onDone" />
      <div class="divider"></div>
      <button class="btn sm ghost" @click="stage = 'learn'">📖 Volver a la explicación</button>
    </div>

    <div v-else class="card" style="max-width:720px">
      <div class="row" style="gap:20px">
        <ScoreRing :value="result.score" />
        <div>
          <h2>{{ result.score >= 90 ? '¡Dominado!' : result.score >= 70 ? '¡Lección superada!' : 'Necesita un poco más de práctica' }}</h2>
          <p class="muted" v-if="result.mistakes.length">{{ result.mistakes.length }} errores añadidos a tu repaso espaciado.</p>
        </div>
      </div>
      <div v-for="(m, k) in result.mistakes" :key="k" class="ex">
        <s class="muted">{{ m.original }}</s> → <b>{{ m.corrected }}</b><br /><small>{{ m.explanation }}</small>
      </div>
      <div class="row" style="margin-top:16px">
        <button class="btn" @click="retry">🔁 Repetir</button>
        <button class="btn primary" :disabled="loadingMore" @click="more"><span v-if="loadingMore" class="spin"></span> ✨ Ejercicios nuevos con IA</button>
        <router-link to="/gramatica" class="btn">Siguiente lección</router-link>
      </div>
    </div>
  </div>
  <div v-else class="empty"><span class="spin"></span></div>
</template>

<style scoped>
.ex { padding: 8px 0; border-bottom: 1px solid var(--border); }
.ex:last-child { border-bottom: none; }
</style>
