<script setup lang="ts">
// Dictogloss: escuchas un texto corto 2 veces (anotando palabras clave) y lo reconstruyes.
import { ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import { speak } from '../composables/audio'

const app = useApp()
const item = ref<any>(null)
const loading = ref(false)
const plays = ref(0)
const notes = ref('')
const attempt = ref('')
const res = ref<any>(null)
const evaluating = ref(false)
const stage = ref<'listen' | 'write' | 'result'>('listen')

async function load() {
  loading.value = true
  res.value = null; notes.value = ''; attempt.value = ''; plays.value = 0; stage.value = 'listen'
  try { item.value = await api.post('/listening/dictogloss', { lang: app.lang, level: app.level }) }
  catch (e: any) { app.notify(e.message, 'error') }
  loading.value = false
}
async function play() {
  plays.value++
  await speak(item.value.text, { random: true })
}
async function check() {
  evaluating.value = true
  try {
    res.value = await api.post('/listening/retell', { lang: app.lang, original: item.value.text, text: attempt.value, source: 'dictogloss' })
    stage.value = 'result'
  } catch (e: any) { app.notify(e.message, 'error') }
  evaluating.value = false
}
</script>

<template>
  <div class="card">
    <p class="muted"><b>Cómo funciona:</b> escuchas un texto corto dos veces a velocidad normal. Mientras, anota solo palabras clave. Luego reconstruye el texto completo con buena gramática. No tiene que ser idéntico: tiene que decir lo mismo y estar bien escrito.</p>
    <button v-if="!item" class="btn primary" :disabled="loading" @click="load"><span v-if="loading" class="spin"></span> Empezar dictogloss</button>
    <template v-else>
      <div v-if="stage === 'listen'">
        <div class="row">
          <button class="btn primary lg" :disabled="plays >= 2" @click="play">🔊 Escuchar ({{ plays }}/2)</button>
          <button class="btn" :disabled="plays < 1" @click="stage = 'write'">Reconstruir →</button>
        </div>
        <textarea v-model="notes" rows="3" placeholder="Notas: solo palabras clave…" style="margin-top:12px"></textarea>
      </div>
      <div v-else-if="stage === 'write'">
        <small class="muted">Tus notas: {{ notes || '—' }}</small>
        <textarea v-model="attempt" rows="5" placeholder="Reconstruye el texto completo…" style="margin-top:8px"></textarea>
        <button class="btn primary" style="margin-top:8px" :disabled="attempt.trim().length < 10 || evaluating" @click="check"><span v-if="evaluating" class="spin"></span> Comparar</button>
      </div>
      <div v-else>
        <div class="row"><span class="chip">🎯 Ideas {{ res.content_score }}</span><span class="chip">✍️ Lengua {{ res.language_score }}</span></div>
        <p>{{ res.feedback }}</p>
        <p><b>Original:</b> {{ item.text }} <button class="btn sm ghost" @click="speak(item.text)">🔊</button><br /><small class="muted">{{ item.es }}</small></p>
        <p v-if="item.focus" class="muted">🎯 Enfoque: {{ item.focus }}</p>
        <p><b>Tu versión:</b> {{ attempt }}</p>
        <div v-for="(c, k) in res.corrections" :key="k" class="crow"><s class="muted">{{ c.original }}</s> → <b>{{ c.corrected }}</b> <small>{{ c.explanation }}</small></div>
        <button class="btn primary" style="margin-top:12px" @click="load">Otro texto →</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.crow { padding: 6px 0; border-bottom: 1px solid var(--border); }
</style>
