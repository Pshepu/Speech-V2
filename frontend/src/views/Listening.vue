<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import { speak } from '../composables/audio'
import PlayButton from '../components/PlayButton.vue'

const app = useApp()
const tab = ref<'pairs' | 'dictation'>('pairs')

// ---------- Pares mínimos (entrenamiento fonético de alta variabilidad) ----------
const contrasts = ref<any[]>([])
const contrast = ref<any>(null)
const ROUNDS = 12
const round = ref(0)
const current = ref<{ pair: string[]; idx: number; voice?: string } | null>(null)
const answered = ref<null | boolean>(null)
const correct = ref(0)
const finished = ref(false)

onMounted(async () => { contrasts.value = await api.get(`/practice/minimal-pairs?lang=${app.lang}`) })

function startContrast(c: any) {
  contrast.value = c; round.value = 0; correct.value = 0; finished.value = false
  nextRound()
}
function nextRound() {
  answered.value = null
  const pair = contrast.value.pairs[Math.floor(Math.random() * contrast.value.pairs.length)]
  const voices = app.langInfo.voices
  current.value = { pair, idx: Math.random() < 0.5 ? 0 : 1, voice: voices[Math.floor(Math.random() * voices.length)] }
  play()
}
function play() { if (current.value) speak(current.value.pair[current.value.idx], { voice: current.value.voice }) }
function answer(i: number) {
  if (answered.value !== null || !current.value) return
  answered.value = i === current.value.idx
  if (answered.value) correct.value++
}
async function next() {
  round.value++
  if (round.value >= ROUNDS) {
    finished.value = true
    await api.post('/practice/listen-result', { lang: app.lang, kind: 'listening', correct: correct.value, total: ROUNDS, detail: { contrast: contrast.value.id } })
  } else nextRound()
}
const voiceName = computed(() => current.value?.voice?.split('-').slice(0, 2).join('-'))

// ---------- Dictado ----------
const dict = ref<any>(null)
const typed = ref('')
const checked = ref<any[] | null>(null)
const dictCount = ref(0)
const dictScore = ref<number[]>([])
async function newDictation() {
  checked.value = null; typed.value = ''
  dict.value = await api.get(`/practice/sentence?lang=${app.lang}&level=${app.level}`)
  setTimeout(() => speak(dict.value.text, { random: true }), 200)
}
const norm = (s: string) => s.toLowerCase().replace(/[’]/g, "'").replace(/[^\p{L}\p{N}']/gu, '')
function checkDictation() {
  const exp = dict.value.text.split(/\s+/)
  const got = typed.value.split(/\s+/).map(norm)
  checked.value = exp.map((w: string, i: number) => ({ w, ok: got.includes(norm(w)) && (got[i] === norm(w) || got.indexOf(norm(w)) !== -1) }))
  const acc = Math.round((100 * checked.value.filter((x) => x.ok).length) / exp.length)
  dictScore.value.push(acc)
  dictCount.value++
  if (dictCount.value % 3 === 0) {
    api.post('/practice/listen-result', { lang: app.lang, kind: 'dictation', correct: dictScore.value.filter((s) => s >= 80).length, total: 3 })
  }
}
</script>

<template>
  <div>
    <div class="page-head">
      <div><h1>👂 Entrena el oído</h1><p>Si no distingues un sonido al escucharlo, no podrás pronunciarlo. Aquí lo oyes con muchas voces y acentos distintos.</p></div>
    </div>
    <div class="tabs">
      <button :class="{ on: tab === 'pairs' }" @click="tab = 'pairs'">Pares mínimos</button>
      <button :class="{ on: tab === 'dictation' }" @click="tab = 'dictation'; if (!dict) newDictation()">Dictado</button>
    </div>

    <template v-if="tab === 'pairs'">
      <div v-if="!contrast" class="grid three">
        <button v-for="c in contrasts" :key="c.id" class="card contrast" @click="startContrast(c)">
          <div class="row between"><b>{{ c.name }}</b><span v-if="c.recommended" class="chip bad">recomendado</span></div>
          <div class="ipa-pair">/{{ c.a }}/ vs /{{ c.b }}/</div>
          <small class="muted">{{ c.pairs.slice(0, 3).map((p: string[]) => p.join('–')).join(', ') }}…</small>
        </button>
      </div>
      <div v-else class="card game">
        <div class="row between">
          <button class="btn sm ghost" @click="contrast = null">← Contrastes</button>
          <small class="muted">{{ contrast.name }} · ronda {{ Math.min(round + 1, ROUNDS) }}/{{ ROUNDS }} · ✓ {{ correct }}</small>
        </div>
        <div class="progress" style="margin:12px 0 24px"><div :style="{ width: (100 * round) / ROUNDS + '%' }"></div></div>
        <template v-if="!finished && current">
          <div class="center">
            <button class="btn lg primary" @click="play">🔊 Escuchar otra vez</button>
            <div><small class="muted">Voz: {{ voiceName }}</small></div>
            <p style="margin-top:20px">¿Qué palabra oíste?</p>
            <div class="row" style="justify-content:center">
              <button v-for="(w, i) in current.pair" :key="w" class="btn lg choice"
                      :class="answered !== null ? (i === current.idx ? 'good' : 'bad') : ''" @click="answer(i)">{{ w }}</button>
            </div>
            <div v-if="answered !== null" style="margin-top:18px">
              <b>{{ answered ? '✅ ¡Correcto!' : `❌ Era “${current.pair[current.idx]}”` }}</b>
              <div class="row" style="justify-content:center;margin-top:8px">
                <PlayButton :text="current.pair[0]" :label="current.pair[0]" />
                <PlayButton :text="current.pair[1]" :label="current.pair[1]" />
                <button class="btn primary" @click="next">Siguiente →</button>
              </div>
            </div>
          </div>
        </template>
        <div v-else class="center">
          <h2>{{ correct }}/{{ ROUNDS }} correctas</h2>
          <p class="muted">{{ correct >= 11 ? '¡Tu oído ya distingue este contraste!' : correct >= 8 ? 'Vas bien; repite mañana para consolidar.' : 'Este contraste te cuesta: repítelo varios días seguidos.' }}</p>
          <p class="muted"><b>/{{ contrast.a }}/</b>: {{ contrast.tip_a.how }}</p>
          <div class="row" style="justify-content:center"><button class="btn" @click="contrast = null">Otro contraste</button><button class="btn primary" @click="startContrast(contrast)">Repetir</button></div>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="card" v-if="dict">
        <p class="muted">Escucha (voz aleatoria) y escribe exactamente lo que oyes.</p>
        <div class="row">
          <button class="btn primary" @click="speak(dict.text, { random: true })">🔊 Escuchar</button>
          <PlayButton :text="dict.text" :rate="-35" label="Lento" size="" />
        </div>
        <textarea v-model="typed" placeholder="Escribe aquí…" style="margin-top:14px" :disabled="!!checked" @keydown.enter.prevent="!checked && checkDictation()"></textarea>
        <div v-if="checked" class="big-text" style="margin-top:14px;font-size:1.25rem">
          <span v-for="(c, i) in checked" :key="i" :class="c.ok ? 'score-good' : 'score-bad'" style="margin-right:6px">{{ c.w }}</span>
          <div class="muted" style="font-size:.95rem">🇪🇸 {{ dict.translation }}</div>
        </div>
        <div class="row" style="margin-top:14px">
          <button v-if="!checked" class="btn primary" :disabled="!typed.trim()" @click="checkDictation">Comprobar</button>
          <button v-else class="btn primary" @click="newDictation">Siguiente →</button>
          <small class="muted" v-if="dictScore.length">Aciertos: {{ dictScore.join('% · ') }}%</small>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.contrast { text-align: left; font: inherit; color: var(--text); cursor: pointer; }
.contrast:hover { border-color: var(--accent); }
.ipa-pair { font-family: var(--mono); font-size: 1.4rem; margin: 6px 0; }
.center { text-align: center; }
.choice { min-width: 140px; font-size: 1.3rem; }
</style>
