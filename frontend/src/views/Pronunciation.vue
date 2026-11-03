<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import { speak, playBlob } from '../composables/audio'
import RecordButton from '../components/RecordButton.vue'
import PlayButton from '../components/PlayButton.vue'
import ScoreRing from '../components/ScoreRing.vue'

const app = useApp()
const level = ref(app.level)
const sentence = ref<any>(null)
const showIpa = ref(false)
const showTr = ref(false)
const custom = ref('')
const useCustom = ref(false)
const result = ref<any>(null)
const busy = ref(false)
const lastBlob = ref<Blob | null>(null)
const selWord = ref<number | null>(null)
const weak = ref<any[]>([])
const focus = ref<string | null>(null)
const recBtn = ref<any>(null)
const history = ref<number[]>([])

async function load() {
  result.value = null; selWord.value = null
  const q = new URLSearchParams({ lang: app.lang, level: level.value })
  if (focus.value) q.set('phoneme', focus.value)
  sentence.value = await api.get(`/practice/sentence?${q}`)
}
async function loadWeak() { weak.value = await api.get(`/practice/weak?lang=${app.lang}`) }
onMounted(() => { load(); loadWeak() })

function useMine() {
  if (!custom.value.trim()) return
  sentence.value = { text: custom.value.trim(), translation: '', level: '', words: [] }
  result.value = null
}

async function onRecorded(blob: Blob) {
  lastBlob.value = blob
  busy.value = true
  try {
    result.value = await api.form('/practice/assess', { audio: blob, text: sentence.value.text, lang: app.lang })
    history.value.push(result.value.score)
    loadWeak()
  } catch (e: any) { app.notify(e.message, 'error') }
  busy.value = false
}

async function shadow() {
  // Shadowing: escuchas al nativo y repites justo después.
  await speak(sentence.value.text)
  recBtn.value?.toggle()
}

const cls = (s: number) => (s >= 80 ? 'good' : s >= 60 ? 'mid' : 'bad')
function pickFocus(p: string | null) { focus.value = p; load() }
</script>

<template>
  <div>
    <div class="page-head">
      <div><h1>🎙️ Pronunciación</h1><p>Evaluación sonido por sonido: el sistema escucha los fonemas reales que produces, no adivina la palabra.</p></div>
      <div class="row">
        <button v-for="l in app.meta.levels" :key="l" class="chip" :class="{ on: level === l }" @click="level = l; load()">{{ l }}</button>
      </div>
    </div>

    <div v-if="weak.length" class="card flat weak">
      <b>Tus sonidos débiles:</b>
      <button v-for="w in weak" :key="w.phoneme" class="chip" :class="focus === w.phoneme ? 'on' : 'bad'" @click="pickFocus(focus === w.phoneme ? null : w.phoneme)">
        /{{ w.phoneme }}/ {{ w.name !== 'sonido' ? w.name : '' }} · {{ Math.round(w.avg) }}
      </button>
      <small class="muted">Toca uno para practicar frases que lo contienen.</small>
    </div>

    <div class="card sentence-card" v-if="sentence">
      <div class="row between" style="margin-bottom:8px">
        <small class="muted">{{ focus ? `Practicando /${focus}/` : sentence.level ? `Nivel ${sentence.level}` : 'Tu frase' }}</small>
        <div class="row">
          <button class="chip" :class="{ on: showIpa }" @click="showIpa = !showIpa">IPA</button>
          <button class="chip" :class="{ on: showTr }" @click="showTr = !showTr" v-if="sentence.translation">Traducción</button>
        </div>
      </div>
      <div class="big-text">
        <template v-if="result">
          <span v-for="(w, i) in result.words" :key="i" class="word" :class="['bg-' + cls(w.score), { sel: selWord === i }]" @click="selWord = selWord === i ? null : i">{{ w.word }}</span>
        </template>
        <template v-else>{{ sentence.text }}</template>
      </div>
      <div v-if="showIpa" class="ipa" style="margin-top:6px">/{{ sentence.ipa || result?.expected_ipa }}/</div>
      <div v-if="showTr" class="muted" style="margin-top:6px">🇪🇸 {{ sentence.translation }}</div>

      <div class="row controls">
        <PlayButton :text="sentence.text" label="Escuchar" size="" />
        <PlayButton :text="sentence.text" :rate="-35" label="Lento" size="" />
        <PlayButton :text="sentence.text" :random="true" label="Otro acento" size="" />
        <div class="grow"></div>
        <button class="btn" :disabled="busy" title="Escucha y repite justo después" @click="shadow">🪞 Shadowing</button>
        <RecordButton ref="recBtn" :busy="busy" @recorded="onRecorded" />
      </div>
    </div>

    <div v-if="result" class="grid two" style="margin-top:16px">
      <div class="card">
        <div class="row" style="gap:18px">
          <ScoreRing :value="result.score" label="global" />
          <div>
            <div><b>{{ result.score >= 85 ? '¡Excelente!' : result.score >= 70 ? 'Muy bien' : result.score >= 55 ? 'Vas bien, sigue' : 'Hay que trabajarlo' }}</b></div>
            <small class="muted" v-if="result.fluency?.wpm">🗣️ {{ result.fluency.wpm }} palabras/min · {{ result.fluency.long_pauses }} pausas largas</small><br />
            <small class="muted" v-if="result.transcript">Whisper entendió: “{{ result.transcript }}”</small>
            <small class="muted" v-if="result.engine !== 'phoneme'"><br />⚠️ Modo básico (sin modelo de fonemas): evaluación por palabra.</small>
          </div>
        </div>
        <div class="row" style="margin-top:14px">
          <button class="btn sm" v-if="lastBlob" @click="playBlob(lastBlob!)">▶️ Mi grabación</button>
          <PlayButton :text="sentence.text" label="Nativo" />
          <div class="grow"></div>
          <button class="btn sm primary" @click="load">Siguiente frase →</button>
        </div>
        <div v-if="history.length > 1" class="muted" style="margin-top:10px"><small>Esta sesión: {{ history.map(Math.round).join(' → ') }}</small></div>

        <div v-if="selWord !== null && result.words[selWord]" class="phones">
          <div class="row between"><b>{{ result.words[selWord].word }}</b> <span class="ipa">/{{ result.words[selWord].ipa }}/</span> <PlayButton :text="result.words[selWord].word" /></div>
          <div class="row" style="margin-top:8px">
            <div v-for="(p, k) in result.words[selWord].phones" :key="k" class="phone" :class="'bg-' + cls(p.score)">
              <div class="ipa-big">{{ p.phone }}</div>
              <small>{{ Math.round(p.score) }}</small>
              <small v-if="p.heard" class="heard">oí /{{ p.heard }}/</small>
            </div>
          </div>
        </div>
        <small v-else class="muted" style="display:block;margin-top:12px">👆 Toca una palabra de la frase para ver cada sonido.</small>
      </div>

      <div class="card">
        <h3>Cómo mejorar</h3>
        <div v-if="!result.tips?.length" class="muted">¡Sin sonidos problemáticos en esta frase! 🎉</div>
        <div v-for="t in result.tips" :key="t.phone" class="tip">
          <div class="row between">
            <b>/{{ t.phone }}/ · {{ t.name }}</b>
            <span class="chip bad">{{ Math.round(t.score) }}</span>
          </div>
          <small class="muted">en “{{ t.word }}”<span v-if="t.heard"> · sonó como /{{ t.heard }}/</span></small>
          <p style="margin:6px 0">{{ t.how }}</p>
          <div class="row" v-if="t.pairs?.length">
            <button v-for="p in t.pairs" :key="p" class="chip on" @click="speak(p.replace(' / ', ', '))">🔊 {{ p }}</button>
          </div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h3>✍️ Practica tu propia frase</h3>
      <div class="row"><input type="text" v-model="custom" placeholder="Escribe cualquier frase que quieras practicar" style="flex:1" @keydown.enter="useMine" />
        <button class="btn" @click="useMine">Usar</button></div>
    </div>
  </div>
</template>

<style scoped>
.weak { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; }
.sentence-card { padding: 26px; }
.word { display: inline-block; padding: 0 5px; margin: 2px; border-radius: 6px; cursor: pointer; border: 2px solid transparent; }
.word.sel { border-color: var(--accent); }
.controls { margin-top: 20px; }
.grow { flex: 1; }
.phones { margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--border); }
.phone { min-width: 54px; padding: 6px 8px; border-radius: 10px; text-align: center; display: flex; flex-direction: column; }
.ipa-big { font-family: var(--mono); font-size: 1.3rem; }
.heard { color: var(--bad); font-weight: 600; }
.tip { padding: 10px 0; border-bottom: 1px solid var(--border); }
.tip:last-child { border-bottom: none; }
</style>
