<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useApp } from '../store'
import { speak } from '../composables/audio'
import RecordButton from '../components/RecordButton.vue'
import PlayButton from '../components/PlayButton.vue'
import ScoreRing from '../components/ScoreRing.vue'

const app = useApp()
const route = useRoute()
const router = useRouter()
const runId = Number(route.params.runId)

const mission = ref<any>(null)
const mode = ref('entrenamiento')
const messages = ref<any[]>([])
const done = ref<string[]>([])
const text = ref('')
const sending = ref(false)
const transcribing = ref(false)
const emotion = ref('friendly')
const complete = ref(false)
const failed = ref(false)
const outOfTurns = ref(false)
const turnsLeft = ref(0)
const hint = ref<any>(null)
const hintLoading = ref(false)
const showPhrases = ref(false)
const audioOnly = ref(false)
const result = ref<any>(null)
const finishing = ref(false)
const chatEl = ref<HTMLElement | null>(null)

const training = computed(() => mode.value === 'entrenamiento')
const EMO: Record<string, string> = { neutral: '😐', happy: '😄', friendly: '🙂', confused: '😕', suspicious: '🤨', annoyed: '😒', impatient: '😤', impressed: '🤩' }

onMounted(async () => {
  const cached = sessionStorage.getItem(`run-${runId}`)
  let data: any
  if (cached) data = JSON.parse(cached)
  else data = await api.get(`/runs/${runId}`)
  mission.value = data.mission
  mode.value = data.mode
  turnsLeft.value = data.mission.max_turns
  if (data.transcript) {
    messages.value = data.transcript
    done.value = data.state?.done || []
    if (data.result) result.value = data.result
  } else {
    messages.value = [{ role: 'assistant', content: data.opening, emotion: 'friendly' }]
    say(data.opening)
  }
  scroll()
})

function say(t: string) { speak(t, { voice: mission.value?.character?.voice }) }
function scroll() { nextTick(() => chatEl.value?.scrollTo({ top: chatEl.value.scrollHeight, behavior: 'smooth' })) }

async function send(content?: string) {
  const msg = (content ?? text.value).trim()
  if (!msg || sending.value) return
  text.value = ''
  hint.value = null
  const userMsg: any = { role: 'user', content: msg }
  messages.value.push(userMsg)
  scroll()
  sending.value = true
  try {
    const r = await api.post(`/runs/${runId}/turn`, { text: msg })
    if (r.correction) userMsg.correction = r.correction
    else if (r.had_correction) userMsg.flag = true
    const m = { role: 'assistant', content: r.reply, emotion: r.emotion, newObjectives: r.new_objectives }
    messages.value.push(m)
    emotion.value = r.emotion
    done.value = r.objectives_done
    turnsLeft.value = r.turns_left
    complete.value = r.mission_complete
    failed.value = r.mission_failed
    outOfTurns.value = r.out_of_turns
    say(r.reply)
    scroll()
  } catch (e: any) {
    app.notify(e.message, 'error')
    messages.value.pop()
    text.value = msg
  }
  sending.value = false
}

async function onRecorded(blob: Blob) {
  transcribing.value = true
  try {
    const last = [...messages.value].reverse().find((m) => m.role === 'assistant')?.content || ''
    const r = await api.form('/stt', { audio: blob, lang: app.lang, prompt: last })
    if (!r.text || r.no_speech > 0.7) app.notify('No te entendí. Intenta de nuevo, más cerca del micrófono.', 'error')
    else await send(r.text)
  } catch (e: any) { app.notify(e.message, 'error') }
  transcribing.value = false
}

async function getHint() {
  hintLoading.value = true
  try { hint.value = await api.post(`/runs/${runId}/hint`) } catch (e: any) { app.notify(e.message, 'error') }
  hintLoading.value = false
}

const translations = ref<Record<number, string>>({})
async function translate(i: number) {
  if (translations.value[i]) { delete translations.value[i]; return }
  try {
    const r = await api.post('/translate', { text: messages.value[i].content, lang: app.lang })
    translations.value[i] = r.translation
  } catch (e: any) { app.notify(e.message, 'error') }
}

async function finish() {
  finishing.value = true
  try { result.value = await api.post(`/runs/${runId}/finish`) } catch (e: any) { app.notify(e.message, 'error') }
  finishing.value = false
  window.scrollTo({ top: 0 })
}

async function addVocab(v: any) {
  await api.post('/cards', { lang: app.lang, kind: 'phrase', front: v.t, back: v.es, source: 'mission' })
  v.added = true
}
</script>

<template>
  <div v-if="mission && !result" class="run">
    <div class="side">
      <div class="card char">
        <div class="avatar">{{ EMO[emotion] || '🙂' }}</div>
        <div><b>{{ mission.character.name }}</b><br /><small class="muted">{{ mission.character.role }}</small></div>
      </div>
      <div class="card">
        <div class="tag">{{ mission.free ? 'CONVERSACIÓN' : 'OBJETIVOS' }}</div>
        <div v-for="o in mission.objectives" :key="o.id" class="obj" :class="{ ok: done.includes(o.id) }">
          {{ done.includes(o.id) ? '✅' : '⬜' }} {{ o.text }}
        </div>
        <div class="progress" style="margin-top:10px"><div :style="{ width: (100 * done.length) / mission.objectives.length + '%' }"></div></div>
        <small class="muted">Turnos restantes: {{ turnsLeft }}</small>
      </div>
      <div v-if="training && mission.useful_phrases?.length" class="card">
        <button class="btn sm ghost" @click="showPhrases = !showPhrases">💡 Frases útiles {{ showPhrases ? '▴' : '▾' }}</button>
        <div v-if="showPhrases" class="stack" style="margin-top:8px">
          <div v-for="p in mission.useful_phrases" :key="p.t" class="phrase">
            <div class="row between"><b>{{ p.t }}</b><PlayButton :text="p.t" /></div><small class="muted">{{ p.es }}</small>
          </div>
        </div>
      </div>
      <div class="card stack">
        <label class="row"><input type="checkbox" v-model="audioOnly" /> 🎧 Solo audio (ocultar texto)</label>
        <button class="btn" :disabled="finishing" @click="finish"><span v-if="finishing" class="spin"></span> 🏁 Terminar e ir al informe</button>
      </div>
    </div>

    <div class="card chat-card">
      <div class="head"><b>{{ mission.title }}</b> <small class="muted">· {{ mission.location }}</small> <span class="chip" :class="training ? 'on' : 'mission'">{{ training ? '🛡️ Entrenamiento' : '🔥 Inmersión' }}</span></div>
      <div ref="chatEl" class="chat">
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="bubble">
            <template v-if="m.role === 'assistant' && audioOnly && !m.reveal">
              <button class="btn sm" @click="m.reveal = true">👁️ Mostrar texto</button>
            </template>
            <template v-else>{{ m.content }}</template>
            <div v-if="m.role === 'assistant'" class="tools">
              <button class="btn sm ghost" @click="say(m.content)">🔊</button>
              <button class="btn sm ghost" @click="speak(m.content, { voice: mission.character.voice, rate: -30 })">🐢</button>
              <button v-if="training" class="btn sm ghost" @click="translate(i)">🇪🇸</button>
            </div>
            <div v-if="translations[i]" class="tr">{{ translations[i] }}</div>
          </div>
          <div v-if="m.correction" class="correction">
            💡 <s>{{ m.correction.original }}</s> → <b>{{ m.correction.corrected }}</b>
            <div><small>{{ m.correction.explanation }}</small></div>
          </div>
          <div v-else-if="m.flag" class="correction subtle"><small>📝 Hay algo que mejorar aquí (lo verás en el informe)</small></div>
          <div v-if="m.newObjectives?.length" class="obj-done">🎯 ¡Objetivo cumplido!</div>
        </div>
        <div v-if="sending" class="msg assistant"><div class="bubble"><span class="spin"></span></div></div>
      </div>

      <div v-if="complete || failed || outOfTurns" class="banner" :class="complete ? 'bg-good' : 'bg-bad'">
        <b>{{ complete ? '🎉 ¡Misión cumplida!' : failed ? '❌ Misión fallida' : '⏱️ Se acabaron los turnos' }}</b>
        <button class="btn primary" :disabled="finishing" @click="finish"><span v-if="finishing" class="spin"></span> Ver informe</button>
      </div>

      <div v-if="hint" class="hint">
        <div v-for="s in hint.suggestions" :key="s.t" class="row between">
          <span><b class="clickable" @click="text = s.t">{{ s.t }}</b> <small class="muted">— {{ s.es }}</small></span><PlayButton :text="s.t" />
        </div>
        <small v-if="hint.tip" class="muted">💡 {{ hint.tip }}</small>
      </div>

      <div class="composer">
        <RecordButton label="Hablar" :busy="transcribing" :disabled="sending" :max-seconds="40" @recorded="onRecorded" />
        <input type="text" v-model="text" placeholder="…o escribe tu respuesta" :disabled="sending" @keydown.enter="send()" />
        <button class="btn primary" :disabled="!text.trim() || sending" @click="send()">Enviar</button>
        <button v-if="training" class="btn" :disabled="hintLoading" title="Pista" @click="getHint"><span v-if="hintLoading" class="spin"></span><span v-else>🆘</span></button>
      </div>
    </div>
  </div>

  <div v-else-if="result" class="debrief">
    <div class="card">
      <div class="tag">INFORME POST-MISIÓN (AAR)</div>
      <div class="row" style="gap:20px">
        <ScoreRing :value="result.score" :size="110" label="puntos" />
        <div style="flex:1">
          <h1>{{ result.success ? '✅ Misión cumplida' : '⏹️ Misión incompleta' }}</h1>
          <p>{{ result.summary }}</p>
          <div class="row">
            <span class="chip">🎯 {{ result.objectives_done.length }}/{{ result.objectives_total }} objetivos</span>
            <span class="chip">🎯 Precisión {{ result.accuracy ?? '–' }}</span>
            <span class="chip">🗣️ Fluidez {{ result.fluency ?? '–' }}</span>
            <span class="chip good" v-if="result.xp">+{{ result.xp }} XP</span>
          </div>
        </div>
      </div>
    </div>
    <div class="grid two" style="margin-top:16px">
      <div class="card" v-if="result.strengths?.length"><h3>💪 Lo que hiciste bien</h3><ul><li v-for="s in result.strengths" :key="s">{{ s }}</li></ul></div>
      <div class="card" v-if="result.improvements?.length"><h3>🎯 A mejorar</h3><ul><li v-for="s in result.improvements" :key="s">{{ s }}</li></ul></div>
    </div>
    <div class="card" v-if="result.corrections?.length">
      <h3>📝 Errores (ya añadidos a tu repaso)</h3>
      <div v-for="(c, k) in result.corrections" :key="k" class="corr-row">
        <div><s class="muted">{{ c.original }}</s> → <b>{{ c.corrected }}</b> <PlayButton :text="c.corrected" /></div>
        <small>{{ c.explanation }} <span class="chip">{{ c.category }}</span></small>
      </div>
    </div>
    <div class="card" v-if="result.better_versions?.length">
      <h3>✨ Cómo lo diría un nativo</h3>
      <div v-for="(b, k) in result.better_versions" :key="k" class="corr-row">
        <div><span class="muted">{{ b.original }}</span><br />→ <b>{{ b.better }}</b> <PlayButton :text="b.better" /></div>
        <small>{{ b.why }}</small>
      </div>
    </div>
    <div class="card" v-if="result.new_vocab?.length">
      <h3>📚 Vocabulario útil de esta situación</h3>
      <div v-for="v in result.new_vocab" :key="v.t" class="row between corr-row">
        <span><b>{{ v.t }}</b> — {{ v.es }}</span>
        <div class="row"><PlayButton :text="v.t" /><button class="btn sm" :disabled="v.added" @click="addVocab(v)">{{ v.added ? '✓ Añadida' : '+ Repaso' }}</button></div>
      </div>
    </div>
    <div class="row" style="margin-top:16px">
      <button class="btn" @click="router.push('/misiones')">← Misiones</button>
      <button v-if="!mission?.free" class="btn mission" @click="router.push(`/misiones?start=${mission?.id}`)">🔁 Repetir misión</button>
      <button class="btn primary" @click="router.push('/')">Volver a Hoy</button>
    </div>
  </div>
  <div v-else class="empty"><span class="spin"></span></div>
</template>

<style scoped>
.run { display: grid; grid-template-columns: 280px 1fr; gap: 16px; align-items: start; }
@media (max-width: 960px) { .run { grid-template-columns: 1fr; } .side { order: 2; } }
.side .card + .card { margin-top: 12px; }
.char { display: flex; gap: 12px; align-items: center; }
.avatar { width: 54px; height: 54px; border-radius: 50%; background: var(--mission-2); display: grid; place-items: center; font-size: 30px; flex: none; }
.tag { font-family: var(--mono); font-size: .72rem; letter-spacing: .12em; color: var(--mission); margin-bottom: 8px; }
.obj { padding: 4px 0; font-size: .93rem; }
.obj.ok { color: var(--good); }
.phrase { border-bottom: 1px solid var(--border); padding-bottom: 6px; }
.chat-card { display: flex; flex-direction: column; padding: 0; height: calc(100vh - 80px); min-height: 520px; }
.chat-card .head { padding: 14px 18px; border-bottom: 1px solid var(--border); display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.chat { flex: 1; overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 12px; }
.msg { display: flex; flex-direction: column; max-width: 80%; }
.msg.user { align-self: flex-end; align-items: flex-end; }
.bubble { padding: 10px 14px; border-radius: 16px; background: var(--surface-2); font-size: 1.02rem; }
.msg.user .bubble { background: var(--accent); color: var(--accent-text); border-bottom-right-radius: 4px; }
.msg.assistant .bubble { border-bottom-left-radius: 4px; }
.tools { display: flex; gap: 2px; margin: 4px -6px -4px; }
.tr { margin-top: 6px; font-size: .9rem; color: var(--muted); border-top: 1px solid var(--border); padding-top: 6px; }
.correction { margin-top: 6px; background: var(--warn-2); color: var(--text); padding: 8px 12px; border-radius: 10px; font-size: .92rem; max-width: 100%; }
.correction.subtle { background: transparent; padding: 2px; }
.obj-done { margin-top: 6px; font-size: .85rem; color: var(--good); font-weight: 600; }
.banner { display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; gap: 10px; }
.hint { padding: 10px 18px; border-top: 1px solid var(--border); background: var(--accent-2); }
.clickable { cursor: pointer; text-decoration: underline dotted; }
.composer { display: flex; gap: 8px; padding: 12px; border-top: 1px solid var(--border); align-items: center; }
.composer input { flex: 1; }
@media (max-width: 600px) { .composer { flex-wrap: wrap; } .composer input { order: 3; flex-basis: 100%; } }
.corr-row { padding: 8px 0; border-bottom: 1px solid var(--border); }
.debrief .card + .card { margin-top: 16px; }
</style>
