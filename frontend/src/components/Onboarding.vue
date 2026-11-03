<script setup lang="ts">
import { ref } from 'vue'
import { useApp } from '../store'
import { api } from '../api'

const app = useApp()
const step = ref(0)
const lang = ref(app.lang)
const level = ref('A1')
const minutes = ref(20)
const saving = ref(false)

const levels = [
  { id: 'A1', t: 'Empiezo de cero', d: 'Sé muy poco o nada.' },
  { id: 'A2', t: 'Básico', d: 'Me presento, pido cosas simples, entiendo frases lentas.' },
  { id: 'B1', t: 'Intermedio', d: 'Me defiendo de viaje, cuento experiencias, con errores.' },
  { id: 'B2', t: 'Intermedio alto', d: 'Converso con nativos con fluidez, me cuestan los detalles.' },
  { id: 'C1', t: 'Avanzado', d: 'Entiendo casi todo; quiero pulir naturalidad y acento.' },
]

async function finish() {
  saving.value = true
  await app.save({ lang: lang.value })
  await app.save({ level: level.value, daily_minutes: minutes.value, onboarded: true })
  // Empieza con un mazo inicial de las palabras más frecuentes.
  try { await api.post('/cards/bulk', { lang: lang.value, count: 20 }) } catch {}
  saving.value = false
  location.reload()
}
</script>

<template>
  <div class="overlay">
    <div class="card box">
      <template v-if="step === 0">
        <h1>¡Bienvenido a Speech! 👋</h1>
        <p>Tu entrenador personal de idiomas. Combina lo que la investigación muestra que funciona: <b>misiones de inmersión con personajes</b>, <b>pronunciación evaluada sonido por sonido</b>, <b>repaso espaciado</b>, gramática e input comprensible.</p>
        <label>¿Qué idioma quieres aprender?</label>
        <div class="row" style="margin:10px 0 20px">
          <button v-for="l in app.meta.languages" :key="l.code" class="btn lg" :class="{ primary: lang === l.code }" @click="lang = l.code">{{ l.flag }} {{ l.name }}</button>
        </div>
        <button class="btn primary" @click="step = 1">Siguiente →</button>
      </template>
      <template v-else-if="step === 1">
        <h2>¿Cuál es tu nivel?</h2>
        <p class="muted">No te preocupes, puedes cambiarlo cuando quieras en Ajustes.</p>
        <div class="stack">
          <button v-for="l in levels" :key="l.id" class="lvl" :class="{ on: level === l.id }" @click="level = l.id">
            <b>{{ l.id }} · {{ l.t }}</b><br /><small>{{ l.d }}</small>
          </button>
        </div>
        <div class="row" style="margin-top:20px"><button class="btn" @click="step = 0">←</button><button class="btn primary" @click="step = 2">Siguiente →</button></div>
      </template>
      <template v-else>
        <h2>¿Cuánto tiempo al día?</h2>
        <p class="muted">La constancia gana a la intensidad: 20 minutos diarios rinden más que 3 horas el domingo.</p>
        <div class="row" style="margin:14px 0 22px">
          <button v-for="m in [10, 20, 30, 45, 60]" :key="m" class="btn" :class="{ primary: minutes === m }" @click="minutes = m">{{ m }} min</button>
        </div>
        <div class="row"><button class="btn" @click="step = 1">←</button><button class="btn primary" :disabled="saving" @click="finish"><span v-if="saving" class="spin"></span> Empezar</button></div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(10, 12, 20, .55); display: grid; place-items: center; z-index: 50; padding: 16px; }
.box { max-width: 560px; width: 100%; max-height: 92vh; overflow-y: auto; }
.lvl { display: block; width: 100%; text-align: left; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 10px 14px; font: inherit; color: var(--text); cursor: pointer; }
.lvl.on { border-color: var(--accent); background: var(--accent-2); }
</style>
