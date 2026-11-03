<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import PlayButton from '../components/PlayButton.vue'
import ScoreRing from '../components/ScoreRing.vue'

const app = useApp()
const PROMPTS = [
  'Describe tu día de ayer con detalle.',
  'Escribe un correo a un hotel pidiendo cambiar tu reserva.',
  'Cuenta cuál es tu mayor objetivo para este año y por qué.',
  '¿Qué harías si ganaras la lotería?',
  'Describe tu ciudad a un turista.',
  'Escribe una reseña de la última película que viste.',
  'Explica cómo se prepara tu plato favorito.',
]
const prompt = ref(PROMPTS[Math.floor(Math.random() * PROMPTS.length)])
const text = ref('')
const res = ref<any>(null)
const loading = ref(false)

async function correct() {
  loading.value = true
  try { res.value = await api.post('/writing/correct', { lang: app.lang, text: text.value, prompt: prompt.value }) }
  catch (e: any) { app.notify(e.message, 'error') }
  loading.value = false
}
function another() { prompt.value = PROMPTS[Math.floor(Math.random() * PROMPTS.length)]; text.value = ''; res.value = null }
</script>

<template>
  <div>
    <router-link to="/gramatica" class="btn sm ghost">← Gramática</router-link>
    <div class="page-head" style="margin-top:8px">
      <div><h1>✍️ Escritura libre</h1><p>Escribe en {{ app.langInfo.name.toLowerCase() }} y recibe correcciones explicadas. Cada error va a tu repaso.</p></div>
    </div>
    <div class="card">
      <div class="row between"><b>📝 {{ prompt }}</b><button class="btn sm ghost" @click="another">🎲 Otro tema</button></div>
      <textarea v-model="text" rows="7" placeholder="Escribe aquí (no pasa nada si te equivocas: de eso se trata)…" style="margin-top:10px"></textarea>
      <div class="row" style="margin-top:10px">
        <button class="btn primary" :disabled="text.trim().length < 10 || loading" @click="correct"><span v-if="loading" class="spin"></span> Corregir</button>
        <small class="muted">{{ text.trim().split(/\s+/).filter(Boolean).length }} palabras</small>
      </div>
    </div>
    <template v-if="res">
      <div class="card">
        <div class="row" style="gap:18px">
          <ScoreRing :value="res.score || 0" />
          <p style="flex:1">{{ res.feedback }}</p>
        </div>
      </div>
      <div class="card">
        <h3>Texto corregido <PlayButton :text="res.corrected" /></h3>
        <p>{{ res.corrected }}</p>
        <h3>Versión nativa natural <PlayButton :text="res.natural" /></h3>
        <p>{{ res.natural }}</p>
      </div>
      <div class="card" v-if="res.corrections?.length">
        <h3>Correcciones</h3>
        <div v-for="(c, k) in res.corrections" :key="k" class="crow">
          <s class="muted">{{ c.original }}</s> → <b>{{ c.corrected }}</b> <span class="chip">{{ c.category }}</span>
          <div><small>{{ c.explanation }}</small></div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.crow { padding: 8px 0; border-bottom: 1px solid var(--border); }
</style>
