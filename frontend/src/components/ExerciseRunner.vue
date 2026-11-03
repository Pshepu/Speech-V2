<script setup lang="ts">
// Ejecuta una lista de ejercicios (elegir, completar, ordenar, corregir, traducir).
import { computed, ref, watch } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import PlayButton from './PlayButton.vue'

const props = defineProps<{ exercises: any[] }>()
const emit = defineEmits<{ (e: 'done', r: { score: number; mistakes: any[] }): void }>()
const app = useApp()

const i = ref(0)
const answer = ref('')
const picked = ref<number | null>(null)
const built = ref<string[]>([])
const result = ref<null | { correct: boolean; feedback: string; corrected?: string }>(null)
const checking = ref(false)
const correct = ref(0)
const mistakes = ref<any[]>([])

const ex = computed(() => props.exercises[i.value])
const pool = ref<{ w: string; used: boolean }[]>([])

watch(ex, (e) => {
  answer.value = ''; picked.value = null; built.value = []; result.value = null
  if (e?.type === 'order') {
    const words = [...(e.words || e.answer.split(' '))]
    for (let k = words.length - 1; k > 0; k--) { const j = Math.floor(Math.random() * (k + 1)); [words[k], words[j]] = [words[j], words[k]] }
    pool.value = words.map((w: string) => ({ w, used: false }))
  }
}, { immediate: true })

const norm = (s: string) => s.toLowerCase().replace(/[’]/g, "'").replace(/[^\p{L}\p{N}' ]/gu, '').replace(/\s+/g, ' ').trim()
const typeLabel: Record<string, string> = { choice: 'Elige la opción correcta', fill: 'Completa el hueco', order: 'Ordena las palabras', fix: 'Corrige el error', translate: 'Traduce' }

function useWord(k: number) { pool.value[k].used = true; built.value.push(pool.value[k].w) }
function undoWord() { const w = built.value.pop(); const p = pool.value.find((x) => x.w === w && x.used); if (p) p.used = false }

async function check() {
  const e = ex.value
  let ok = false
  let userAns = ''
  if (e.type === 'choice') { ok = picked.value === e.answer; userAns = e.options[picked.value ?? 0] }
  else if (e.type === 'fill') {
    userAns = answer.value
    const valid = [e.answer, ...(e.accept || [])].map(norm)
    ok = valid.includes(norm(answer.value))
  } else if (e.type === 'order') { userAns = built.value.join(' '); ok = norm(userAns) === norm(e.answer) }
  else {
    userAns = answer.value
    checking.value = true
    try {
      const r = await api.post('/grammar/check-open', { lang: app.lang, type: e.type, prompt: e.prompt, answer: answer.value, expected: e.answer })
      checking.value = false
      result.value = { correct: r.correct, feedback: r.feedback || e.explanation, corrected: r.correct ? undefined : (r.corrected && norm(r.corrected) !== norm(answer.value) ? r.corrected : e.answer) }
      ok = r.correct
    } catch (err: any) {
      checking.value = false
      ok = norm(answer.value) === norm(e.answer)
      result.value = { correct: ok, feedback: e.explanation, corrected: ok ? undefined : e.answer }
    }
  }
  if (!result.value) result.value = { correct: ok, feedback: e.explanation || '', corrected: ok ? undefined : correctText(e) }
  if (ok) correct.value++
  else {
    const promptText = e.type === 'translate' ? userAns : e.type === 'fix' ? userAns || e.prompt : (e.prompt || '').replace('___', userAns || '___')
    mistakes.value.push({ original: promptText, corrected: correctText(e), explanation: e.explanation || '' })
  }
}

function correctText(e: any) {
  if (e.type === 'choice') return (e.prompt || '').includes('___') ? e.prompt.replace('___', e.options[e.answer]) : e.options[e.answer]
  if (e.type === 'fill') return (e.prompt || '').replace('___', e.answer)
  return e.answer
}

function next() {
  if (i.value + 1 >= props.exercises.length) {
    emit('done', { score: Math.round((100 * correct.value) / props.exercises.length), mistakes: mistakes.value })
  } else i.value++
}

const canCheck = computed(() => {
  const e = ex.value
  if (!e) return false
  if (e.type === 'choice') return picked.value !== null
  if (e.type === 'order') return built.value.length > 0
  return answer.value.trim().length > 0
})

function onKey(ev: KeyboardEvent) {
  if (ev.key === 'Enter') { ev.preventDefault(); if (result.value) next(); else if (canCheck.value) check() }
}
</script>

<template>
  <div v-if="ex" class="runner" @keydown="onKey">
    <div class="row between" style="margin-bottom:10px">
      <small class="muted">{{ typeLabel[ex.type] }} · {{ i + 1 }}/{{ exercises.length }}</small>
      <small class="muted">✓ {{ correct }}</small>
    </div>
    <div class="progress" style="margin-bottom:18px"><div :style="{ width: (100 * i) / exercises.length + '%' }"></div></div>

    <div class="prompt">
      <template v-if="ex.type === 'translate'">🇪🇸 {{ ex.prompt }}</template>
      <template v-else-if="ex.type === 'order'">Forma la frase correcta:</template>
      <template v-else>{{ ex.prompt }}</template>
    </div>

    <div v-if="ex.type === 'choice'" class="stack opts">
      <button v-for="(o, k) in ex.options" :key="k" class="opt" :disabled="!!result"
              :class="{ on: picked === k, good: result && k === ex.answer, bad: result && picked === k && k !== ex.answer }"
              @click="picked = k">{{ o }}</button>
    </div>
    <div v-else-if="ex.type === 'order'">
      <div class="built">{{ built.join(' ') || '…' }} <button v-if="built.length && !result" class="btn sm ghost" @click="undoWord">⌫</button></div>
      <div class="row">
        <button v-for="(p, k) in pool" :key="k" class="chip on" :disabled="p.used || !!result" :style="{ opacity: p.used ? .3 : 1 }" @click="useWord(k)">{{ p.w }}</button>
      </div>
    </div>
    <input v-else type="text" v-model="answer" :disabled="!!result" :placeholder="ex.type === 'fix' ? 'Escribe la frase corregida' : 'Tu respuesta'" autofocus @keydown="onKey" />

    <div v-if="result" class="feedback" :class="result.correct ? 'bg-good' : 'bg-bad'">
      <b>{{ result.correct ? '✅ ¡Correcto!' : '❌ No del todo' }}</b>
      <div v-if="result.corrected" class="row" style="margin-top:4px">Respuesta: <b>{{ result.corrected }}</b> <PlayButton :text="result.corrected" /></div>
      <div v-if="result.feedback" style="margin-top:4px">{{ result.feedback }}</div>
    </div>

    <div class="row" style="margin-top:16px">
      <button v-if="!result" class="btn primary" :disabled="!canCheck || checking" @click="check"><span v-if="checking" class="spin"></span> Comprobar</button>
      <button v-else class="btn primary" @click="next">{{ i + 1 >= exercises.length ? 'Ver resultado' : 'Siguiente →' }}</button>
      <small class="muted"><span class="kbd">Enter</span></small>
    </div>
  </div>
</template>

<style scoped>
.prompt { font-size: 1.2rem; font-weight: 600; margin-bottom: 14px; }
.opt { text-align: left; width: 100%; font: inherit; padding: 11px 14px; border-radius: 10px; border: 1px solid var(--border); background: var(--surface); color: var(--text); cursor: pointer; }
.opt.on { border-color: var(--accent); background: var(--accent-2); }
.opt.good { border-color: var(--good); background: var(--good-2); }
.opt.bad { border-color: var(--bad); background: var(--bad-2); }
.built { min-height: 46px; padding: 10px 12px; border: 1px dashed var(--border); border-radius: 10px; margin-bottom: 12px; font-size: 1.1rem; }
.feedback { margin-top: 14px; padding: 12px 14px; border-radius: 10px; }
</style>
