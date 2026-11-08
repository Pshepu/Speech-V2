<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useApp } from '../store'
import { speak } from '../composables/audio'
import RecordButton from '../components/RecordButton.vue'
import PlayButton from '../components/PlayButton.vue'
import ScoreRing from '../components/ScoreRing.vue'
import ClickableText from '../components/ClickableText.vue'

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
const recBtn = ref<any>(null)
const turnsLeftAI = ref<number | null>(null)
const targetWords = ref<any[]>([])
const engineMode = ref('llm')
const wordsUsed = ref<string[]>([])
const myNotes = ref('')
// Práctica posterior: repetir en voz alta cada frase corregida (evaluación local, sin IA).
const post = ref<Record<number, any>>({})
async function sayCorrected(k: number, text: string, blob: Blob) {
  post.value[k] = { busy: true }
  try {
    const r = await api.form('/practice/assess', { audio: blob, text, lang: app.lang, mode: 'mission_post', transcribe: '0' })
    post.value[k] = { score: Math.round(r.score), tips: (r.tips || []).slice(0, 2) }
  } catch (e: any) { post.value[k] = { error: e.message } }
}
async function refreshBudget() { try { turnsLeftAI.value = (await api.get('/budget')).turns_left } catch {} }
const handsFree = ref(false)

function maybeListen() {
  // Manos libres: cuando el personaje termina de hablar, empezamos a escucharte.
  if (handsFree.value && !complete.value && !failed.value && !outOfTurns.value && !result.value) {
    setTimeout(() => recBtn.value?.start(), 250)
  }
}
function toggleHandsFree() {
  handsFree.value = !handsFree.value
  if (handsFree.value) maybeListen()
}

// Autocorrección guiada: primero una pista, luego tú lo intentas (más eficaz que dar la respuesta).
async function checkRetry(m: any) {
  if (!m.retry?.trim()) return
  m.checking = true
  try {
    const r = await api.post('/grammar/check-open', { lang: app.lang, type: 'fix', prompt: m.correction.original, answer: m.retry, expected: m.correction.corrected })
    m.retryResult = r
    m.revealed = true
    if (r.correct) speak(m.retry, { voice: undefined })
  } catch (e: any) { app.notify(e.message, 'error') }
  m.checking = false
}

const training = computed(() => mode.value === 'entrenamiento')
const EMO: Record<string, string> = { neutral: '😐', happy: '😄', friendly: '🙂', confused: '😕', suspicious: '🤨', annoyed: '😒', impatient: '😤', impressed: '🤩' }

onMounted(async () => {
  // La partida se guarda en el servidor turno a turno: siempre se carga desde ahí,
  // así puedes cerrar la app y retomarla más tarde exactamente donde la dejaste.
  const data: any = await api.get(`/runs/${runId}`)
  mission.value = data.mission
  mode.value = data.mode
  messages.value = data.transcript || []
  done.value = data.state?.done || []
  targetWords.value = data.state?.target_words || []
  engineMode.value = data.state?.engine || 'llm'
  wordsUsed.value = data.state?.words_used || []
  myNotes.value = sessionStorage.getItem(`notes-${data.mission.id}`) || ''
  if (data.result && !data.result.abandoned) result.value = data.result
  const userTurns = messages.value.filter((m: any) => m.role === 'user').length
  turnsLeft.value = Math.max(0, data.mission.max_turns - userTurns)
  refreshBudget()
  if (userTurns === 0 && messages.value.length) say(messages.value[0].content)
  else if (userTurns > 0) app.notify('Misión retomada donde la dejaste', 'good')
  scroll()
})

function say(t: string) { return speak(t, { voice: mission.value?.character?.voice }) }
function scroll() { nextTick(() => chatEl.value?.scrollTo({ top: chatEl.value.scrollHeight, behavior: 'smooth' })) }

async function send(content?: string): Promise<any> {
  const msg = (content ?? text.value).trim()
  if (!msg || sending.value) return null
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
    const m = { role: 'assistant', content: r.reply, emotion: r.emotion, newObjectives: r.new_objectives, free: r.engine === 'scene' && engineMode.value === 'scene' }
    messages.value.push(m)
    emotion.value = r.emotion
    done.value = r.objectives_done
    if (r.words_used) wordsUsed.value = r.words_used
    turnsLeft.value = r.turns_left
    complete.value = r.mission_complete
    failed.value = r.mission_failed
    outOfTurns.value = r.out_of_turns
    sending.value = false
    refreshBudget()
    // Si la escena lleva varios turnos sin avanzar, ofrecemos una pista automáticamente.
    if (r.stuck && training.value && !hint.value) getHint()
    scroll()
    say(r.reply).then(maybeListen)
    return userMsg
  } catch (e: any) {
    app.notify(e.message, 'error')
    messages.value.pop()
    text.value = msg
  }
  sending.value = false
  return null
}

async function onRecorded(blob: Blob) {
  transcribing.value = true
  try {
    const last = [...messages.value].reverse().find((m) => m.role === 'assistant')?.content || ''
    const r = await api.form('/stt', { audio: blob, lang: app.lang, prompt: last })
    transcribing.value = false
    if (!r.text || r.no_speech > 0.7) {
      app.notify('No te entendí. Intenta de nuevo, más cerca del micrófono.', 'error')
      maybeListen()
    } else {
      // La pronunciación de tu frase se evalúa en paralelo (sin frenar la conversación).
      const pron = api.form('/practice/assess', { audio: blob, text: r.text, lang: app.lang, mode: 'conversation', transcribe: '0' }).catch(() => null)
      const um = await send(r.text)
      const a = await pron
      if (um && a) { um.pron = Math.round(a.score); um.pronTips = (a.tips || []).slice(0, 2) }
    }
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
        <small v-if="turnsLeftAI !== null" class="muted" style="display:block">⚡ Cuota de IA hoy: ≈ {{ turnsLeftAI }} turnos</small>
      </div>
      <div v-if="targetWords.length" class="card">
        <div class="tag">TUS PALABRAS (BONUS)</div>
        <small class="muted">Úsalas al hablar: cada uso cuenta como repaso.</small>
        <div v-for="w in targetWords" :key="w.id" class="obj" :class="{ ok: wordsUsed.includes(w.front) }">
          {{ wordsUsed.includes(w.front) ? '✅' : '▫️' }} <b>{{ w.front }}</b> <small class="muted">{{ w.back }}</small>
        </div>
      </div>
      <div v-if="myNotes" class="card"><div class="tag">TUS NOTAS</div><small style="white-space:pre-wrap">{{ myNotes }}</small></div>
      <div v-if="training && mission.useful_phrases?.length" class="card">
        <button class="btn sm ghost" @click="showPhrases = !showPhrases">💡 Frases útiles {{ showPhrases ? '▴' : '▾' }}</button>
        <div v-if="showPhrases" class="stack" style="margin-top:8px">
          <div v-for="p in mission.useful_phrases" :key="p.t" class="phrase">
            <div class="row between"><b>{{ p.t }}</b><PlayButton :text="p.t" /></div><small class="muted">{{ p.es }}</small>
          </div>
        </div>
      </div>
      <div class="card stack">
        <button class="btn" :class="{ primary: handsFree }" @click="toggleHandsFree">{{ handsFree ? '🎙️ Manos libres: ON' : '🎙️ Manos libres' }}</button>
        <small class="muted">Habla y espera: se envía solo al detectar silencio, y vuelve a escucharte tras la respuesta.</small>
        <label class="row"><input type="checkbox" v-model="audioOnly" /> 🎧 Solo audio (ocultar texto)</label>
        <button class="btn" :disabled="finishing" @click="finish"><span v-if="finishing" class="spin"></span> 🏁 Terminar e ir al informe</button>
      </div>
    </div>

    <div class="card chat-card">
      <div class="head"><b>{{ mission.title }}</b> <small class="muted">· {{ mission.location }}</small> <span class="chip" :class="training ? 'on' : 'mission'">{{ training ? '🛡️ Entrenamiento' : '🔥 Inmersión' }}</span>
        <span v-if="engineMode === 'scene'" class="chip good" title="La mayoría de respuestas salen de la escena preparada y no gastan cuota">⚡ Modo ahorro</span></div>
      <div ref="chatEl" class="chat">
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="bubble">
            <template v-if="m.role === 'assistant' && audioOnly && !m.reveal">
              <button class="btn sm" @click="m.reveal = true">👁️ Mostrar texto</button>
            </template>
            <template v-else-if="m.role === 'assistant'"><ClickableText :text="m.content" /></template>
            <template v-else>{{ m.content }}</template>
            <div v-if="m.role === 'assistant'" class="tools">
              <button class="btn sm ghost" @click="say(m.content)">🔊</button>
              <button class="btn sm ghost" @click="speak(m.content, { voice: mission.character.voice, rate: -30 })">🐢</button>
              <button v-if="training" class="btn sm ghost" @click="translate(i)">🇪🇸</button>
            </div>
            <div v-if="translations[i]" class="tr">{{ translations[i] }}</div>
          </div>
          <div v-if="m.pron != null" class="pron" :class="m.pron >= 80 ? 'score-good' : m.pron >= 60 ? 'score-mid' : 'score-bad'"
               :title="(m.pronTips || []).map((t: any) => `/${t.phone}/ en ${t.word}`).join(', ')">
            🎙️ pronunciación {{ m.pron }}<span v-if="m.pronTips?.length"> · revisa {{ m.pronTips.map((t: any) => '/' + t.phone + '/').join(' ') }}</span>
          </div>
          <div v-if="m.correction" class="correction">
            <template v-if="!m.revealed && m.correction.hint">
              🤔 <b>Hay algo que corregir.</b> {{ m.correction.hint }}
              <div class="row retry">
                <input type="text" v-model="m.retry" placeholder="Escribe tu frase corregida…" @keydown.enter="checkRetry(m)" />
                <button class="btn sm primary" :disabled="m.checking" @click="checkRetry(m)"><span v-if="m.checking" class="spin"></span> Comprobar</button>
                <button class="btn sm ghost" @click="m.revealed = true">Ver solución</button>
              </div>
            </template>
            <template v-else>
              <div v-if="m.retryResult" :class="m.retryResult.correct ? 'score-good' : 'score-bad'">
                <b>{{ m.retryResult.correct ? '✅ ¡Bien corregido!' : '❌ Casi.' }}</b> {{ m.retryResult.feedback }}
              </div>
              💡 <s>{{ m.correction.original }}</s> → <b>{{ m.correction.corrected }}</b> <PlayButton :text="m.correction.corrected" />
              <div><small>{{ m.correction.explanation }}</small></div>
            </template>
          </div>
          <div v-else-if="m.flag" class="correction subtle"><small>📝 Hay algo que mejorar aquí (lo verás en el informe)</small></div>
          <div v-if="m.newObjectives?.length" class="obj-done">🎯 ¡Objetivo cumplido!</div>
          <small v-if="m.free" class="muted" style="font-size:.72rem">⚡ sin gastar IA</small>
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
        <RecordButton ref="recBtn" label="Hablar" :busy="transcribing" :disabled="sending" :max-seconds="60" :auto-stop="handsFree" @recorded="onRecorded" />
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
            <span v-if="result.scene_turns" class="chip good">⚡ {{ result.scene_turns }}/{{ result.scene_turns + result.ai_turns }} turnos sin gastar IA</span>
            <span v-if="result.target_words?.length" class="chip">📚 Usaste {{ result.words_used.length }}/{{ result.target_words.length }} de tus palabras</span>
          </div>
          <p v-if="result.previous_score != null" style="margin-top:8px">
            🔁 Intento anterior: {{ Math.round(result.previous_score) }} →
            <b :class="result.score >= result.previous_score ? 'score-good' : 'score-mid'">ahora {{ Math.round(result.score) }}
              ({{ result.score >= result.previous_score ? '+' : '' }}{{ Math.round(result.score - result.previous_score) }})</b>
          </p>
        </div>
      </div>
    </div>
    <div class="grid two" style="margin-top:16px">
      <div class="card" v-if="result.strengths?.length"><h3>💪 Lo que hiciste bien</h3><ul><li v-for="s in result.strengths" :key="s">{{ s }}</li></ul></div>
      <div class="card" v-if="result.improvements?.length"><h3>🎯 A mejorar</h3><ul><li v-for="s in result.improvements" :key="s">{{ s }}</li></ul></div>
    </div>
    <div class="card" v-if="result.corrections?.length">
      <h3>📝 Errores (ya añadidos a tu repaso)</h3>
      <small class="muted">Práctica posterior: escucha la versión correcta y dila tú. Fijarla en voz alta ayuda a no repetir el error.</small>
      <div v-for="(c, k) in result.corrections" :key="k" class="corr-row">
        <div><s class="muted">{{ c.original }}</s> → <b>{{ c.corrected }}</b> <PlayButton :text="c.corrected" /></div>
        <small>{{ c.explanation }} <span class="chip">{{ c.category }}</span></small>
        <div class="row" style="margin-top:6px">
          <RecordButton label="🎙️ Dilo bien" :busy="post[k]?.busy" :max-seconds="12" @recorded="(b: Blob) => sayCorrected(k, c.corrected, b)" />
          <span v-if="post[k]?.score != null" :class="post[k].score >= 80 ? 'score-good' : post[k].score >= 60 ? 'score-mid' : 'score-bad'">
            <b>{{ post[k].score }}</b> <small v-if="post[k].tips?.length">· revisa {{ post[k].tips.map((t: any) => '/' + t.phone + '/').join(' ') }}</small>
          </span>
          <small v-if="post[k]?.error" class="score-bad">{{ post[k].error }}</small>
        </div>
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
      <button v-if="!mission?.free" class="btn mission" @click="router.push(`/misiones?start=${mission?.id}`)">🔁 Repetir (con variación)</button>
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
.retry { margin-top: 8px; flex-wrap: nowrap; }
.retry input { flex: 1; min-width: 120px; padding: 6px 10px; }
.pron { font-size: .78rem; margin-top: 3px; font-weight: 600; }
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
