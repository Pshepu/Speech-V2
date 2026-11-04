<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import RecordButton from '../components/RecordButton.vue'

const app = useApp()
const sum = ref<any>(null)
const test = ref<'' | 'vocab' | 'speaking' | 'writing'>('')
const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']

async function load() { sum.value = await api.get(`/assessment/summary?lang=${app.lang}`) }
onMounted(load)

const SKILLS = [
  { id: 'vocabulary', name: 'Vocabulario', icon: '📚', test: 'vocab', how: 'Test de tamaño de vocabulario (3 min)' },
  { id: 'speaking', name: 'Expresión oral', icon: '🗣️', test: 'speaking', how: 'Monólogo de 1-2 minutos evaluado' },
  { id: 'writing', name: 'Expresión escrita', icon: '✍️', test: 'writing', how: 'Redacción evaluada con criterios de examen' },
  { id: 'listening', name: 'Comprensión auditiva', icon: '👂', test: '', how: 'Se calcula con tus resultados en Escucha' },
  { id: 'reading', name: 'Comprensión lectora', icon: '📖', test: '', how: 'Se calcula con tus resultados en Lectura' },
]
const pct = (lvl?: string) => (lvl && LEVELS.includes(lvl) ? ((LEVELS.indexOf(lvl) + 1) / 5) * 100 : 0)

// ---------- Test de vocabulario ----------
const vt = ref<any>(null)
const vi = ref(0)
const known = ref<string[]>([])
const vres = ref<any>(null)
async function startVocab() {
  vres.value = null; known.value = []; vi.value = 0
  try { vt.value = await api.get(`/assessment/vocab-test?lang=${app.lang}`); test.value = 'vocab' }
  catch (e: any) { app.notify(e.message, 'error') }
}
async function answerVocab(yes: boolean) {
  const w = vt.value.items[vi.value]
  if (yes) known.value.push(w)
  vi.value++
  if (vi.value >= vt.value.items.length) {
    vres.value = await api.post('/assessment/vocab-test', { lang: app.lang, shown: vt.value.items, known: known.value })
    load()
  }
}

// ---------- Expresión oral ----------
const prompt = ref<any>(null)
const sres = ref<any>(null)
const sbusy = ref(false)
const plevel = ref(app.level)
async function startPrompt(kind: 'speaking' | 'writing') {
  test.value = kind; sres.value = null; wres.value = null; wtext.value = ''
  prompt.value = await api.get(`/assessment/prompt?skill=${kind}&lang=${app.lang}&level=${plevel.value}`)
}
async function onSpeech(blob: Blob) {
  sbusy.value = true
  try { sres.value = await api.form('/assessment/speaking', { audio: blob, lang: app.lang, prompt: prompt.value.prompt }); load() }
  catch (e: any) { app.notify(e.message, 'error') }
  sbusy.value = false
}

// ---------- Escritura ----------
const wtext = ref('')
const wres = ref<any>(null)
const wbusy = ref(false)
async function submitWriting() {
  wbusy.value = true
  try { wres.value = await api.post('/assessment/writing', { lang: app.lang, prompt: prompt.value.prompt, text: wtext.value }); load() }
  catch (e: any) { app.notify(e.message, 'error') }
  wbusy.value = false
}
const evalRes = computed(() => (test.value === 'speaking' ? sres.value : wres.value))
const CRIT: Record<string, string> = { range: 'Variedad (léxico y estructuras)', accuracy: 'Corrección', fluency_coherence: 'Fluidez y coherencia', task: 'Cumplimiento de la tarea' }
</script>

<template>
  <div>
    <div class="page-head">
      <div><h1>🎯 Mi nivel (camino a C1)</h1><p>Mide cada destreza por separado: casi nadie tiene el mismo nivel en todo. Repite los tests cada 3-4 semanas para ver tu progreso.</p></div>
      <div v-if="sum?.overall" class="overall"><small>Nivel global estimado</small><b>{{ sum.overall }}</b></div>
    </div>

    <template v-if="!test">
      <div v-if="sum" class="grid two">
        <div v-for="s in SKILLS" :key="s.id" class="card skill">
          <div class="row between"><h3 style="margin:0">{{ s.icon }} {{ s.name }}</h3><span class="lvl">{{ sum.skills[s.id]?.level || '—' }}</span></div>
          <div class="ladder">
            <div v-for="l in ['A1','A2','B1','B2','C1']" :key="l" class="step" :class="{ on: pct(sum.skills[s.id]?.level) >= ((['A1','A2','B1','B2','C1'].indexOf(l) + 1) / 5) * 100, goal: l === 'C1' }">{{ l }}</div>
          </div>
          <small class="muted">
            <template v-if="s.id === 'vocabulary' && sum.skills.vocabulary">≈ {{ sum.skills.vocabulary.size }} palabras de las 5.000 más frecuentes (C1 ≈ 3.750-4.500). </template>
            <template v-else-if="(s.id === 'listening' || s.id === 'reading') && sum.skills[s.id]">{{ sum.skills[s.id].samples }} ejercicios evaluados. </template>
            {{ s.how }}
          </small>
          <div class="row" style="margin-top:10px">
            <button v-if="s.test === 'vocab'" class="btn sm primary" @click="startVocab">Hacer el test</button>
            <button v-else-if="s.test" class="btn sm primary" @click="startPrompt(s.test as any)">Hacer la prueba</button>
            <router-link v-else :to="s.id === 'listening' ? '/oido' : '/lectura'" class="btn sm">Ir a practicar</router-link>
          </div>
        </div>
      </div>
      <div class="card" style="margin-top:16px">
        <h3>¿Qué significa C1?</h3>
        <p class="muted">Usuario competente: entiendes textos largos y exigentes, captas sentidos implícitos, te expresas con fluidez y espontaneidad sin buscar palabras, usas el idioma con flexibilidad en lo social, académico y profesional, y produces textos claros y bien estructurados sobre temas complejos.</p>
        <p class="muted">Como orientación, el FSI calcula unas 600-750 horas de clase para que un angloparlante alcance un nivel profesional en idiomas cercanos como el español o el francés. La práctica diaria constante es lo que más cuenta.</p>
      </div>
    </template>

    <div v-else-if="test === 'vocab'" class="card center">
      <button class="btn sm ghost back" @click="test = ''">← Volver</button>
      <template v-if="!vres && vt">
        <p class="muted">¿Conoces esta palabra (sabes qué significa)? Sé honesto: hay palabras inventadas para detectar si dices “sí” a todo.</p>
        <small class="muted">{{ vi + 1 }} / {{ vt.items.length }}</small>
        <div class="progress" style="margin:8px auto 30px;max-width:400px"><div :style="{ width: (100 * vi) / vt.items.length + '%' }"></div></div>
        <div class="word">{{ vt.items[vi] }}</div>
        <div class="row" style="justify-content:center;margin-top:24px">
          <button class="btn lg bad" @click="answerVocab(false)">No la conozco</button>
          <button class="btn lg good" @click="answerVocab(true)">La conozco</button>
        </div>
      </template>
      <template v-else-if="vres">
        <h2>≈ {{ vres.size }} palabras · nivel {{ vres.level }}</h2>
        <p class="muted">Falsas alarmas (palabras inventadas que marcaste): {{ vres.false_alarm }}%{{ vres.false_alarm > 20 ? ' — sé más estricto la próxima vez' : '' }}</p>
        <div class="bands">
          <div v-for="b in vres.bands" :key="b.band" class="bandcol"><div class="bar" :style="{ height: b.adjusted + '%' }"></div><small>{{ b.band }}</small></div>
        </div>
        <p class="muted">Para C1 necesitas dominar casi todas las 4.000-5.000 palabras más frecuentes. Añade palabras desde Vocabulario (por frecuencia) y los paquetes avanzados.</p>
        <button class="btn primary" @click="test = ''">Listo</button>
      </template>
      <div v-else class="empty"><span class="spin"></span></div>
    </div>

    <div v-else class="card">
      <button class="btn sm ghost" @click="test = ''">← Volver</button>
      <div class="row between" style="margin-top:8px">
        <h2 style="margin:0">{{ test === 'speaking' ? '🗣️ Prueba de expresión oral' : '✍️ Prueba de escritura' }}</h2>
        <div class="row"><small class="muted">Nivel de la tarea:</small>
          <select v-model="plevel" style="width:auto" @change="startPrompt(test as any)"><option v-for="l in ['A1','A2','B1','B2','C1']" :key="l">{{ l }}</option></select></div>
      </div>
      <div v-if="prompt" class="task">📝 {{ prompt.prompt }}</div>
      <p class="muted" v-if="test === 'speaking'">Prepara tus ideas 1 minuto si quieres y luego habla 1-2 minutos sin parar, en {{ app.langInfo.name.toLowerCase() }}.</p>
      <div v-if="test === 'speaking' && !sres"><RecordButton label="Empezar a hablar" :busy="sbusy" :max-seconds="180" @recorded="onSpeech" /></div>
      <div v-if="test === 'writing' && !wres">
        <textarea v-model="wtext" rows="10" placeholder="Escribe aquí tu texto…"></textarea>
        <div class="row" style="margin-top:8px"><button class="btn primary" :disabled="wtext.trim().split(/\s+/).length < 30 || wbusy" @click="submitWriting"><span v-if="wbusy" class="spin"></span> Evaluar</button>
          <small class="muted">{{ wtext.trim().split(/\s+/).filter(Boolean).length }} palabras</small></div>
      </div>
      <div v-if="evalRes" class="result">
        <div class="row" style="gap:16px"><div class="biglvl">{{ evalRes.level }}</div><p style="flex:1">{{ evalRes.summary }}</p></div>
        <div v-if="evalRes.metrics" class="row"><span class="chip">🗣️ {{ evalRes.metrics.wpm }} pal/min</span><span class="chip">⏸️ {{ evalRes.metrics.long_pauses }} pausas largas</span><span v-if="evalRes.metrics.pronunciation" class="chip">🎙️ pronunciación {{ Math.round(evalRes.metrics.pronunciation) }}</span></div>
        <div class="crit">
          <div v-for="(v, k) in evalRes.criteria" :key="k" class="critrow"><span>{{ CRIT[k] || k }}</span><div class="progress" style="flex:1"><div :style="{ width: (Number(v) / 5) * 100 + '%' }"></div></div><b>{{ v }}/5</b></div>
        </div>
        <div class="grid two">
          <div><h3>💪 Fortalezas</h3><ul><li v-for="s in evalRes.strengths" :key="s">{{ s }}</li></ul></div>
          <div><h3>🚀 Para subir de nivel</h3><ul><li v-for="s in evalRes.to_reach_next_level" :key="s">{{ s }}</li></ul></div>
        </div>
        <div v-if="evalRes.corrections?.length"><h3>📝 Errores (añadidos a tu repaso)</h3>
          <div v-for="(c, i) in evalRes.corrections" :key="i" class="crow"><s class="muted">{{ c.original }}</s> → <b>{{ c.corrected }}</b> <small>{{ c.explanation }}</small></div></div>
        <div v-if="evalRes.improved"><h3>✨ Tu texto un nivel más arriba</h3><p>{{ evalRes.improved }}</p></div>
        <details v-if="evalRes.transcript"><summary class="muted">Transcripción</summary><p>{{ evalRes.transcript }}</p></details>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overall { text-align: center; background: var(--accent-2); color: var(--accent); padding: 8px 18px; border-radius: 14px; display: flex; flex-direction: column; }
.overall b { font-size: 1.8rem; }
.lvl { font-size: 1.4rem; font-weight: 800; color: var(--accent); }
.ladder { display: flex; gap: 4px; margin: 12px 0 8px; }
.step { flex: 1; text-align: center; padding: 4px 0; border-radius: 6px; background: var(--surface-2); color: var(--muted); font-size: .8rem; font-weight: 700; }
.step.on { background: var(--accent); color: var(--accent-text); }
.step.goal { outline: 2px dashed var(--mission); outline-offset: 1px; }
.center { text-align: center; position: relative; }
.back { position: absolute; left: 12px; top: 12px; }
.word { font-size: 2.4rem; font-weight: 700; }
.bands { display: flex; gap: 10px; align-items: flex-end; justify-content: center; height: 140px; margin: 16px 0; }
.bandcol { display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; width: 70px; }
.bandcol .bar { width: 40px; background: var(--accent); border-radius: 6px 6px 0 0; min-height: 3px; }
.task { font-size: 1.1rem; font-weight: 600; margin: 14px 0; padding: 12px 14px; background: var(--surface-2); border-radius: 10px; }
.result { margin-top: 18px; border-top: 1px solid var(--border); padding-top: 14px; }
.biglvl { font-size: 2.6rem; font-weight: 800; color: var(--accent); }
.crit { margin: 14px 0; }
.critrow { display: flex; align-items: center; gap: 10px; padding: 4px 0; }
.critrow span { width: 230px; font-size: .9rem; }
.crow { padding: 6px 0; border-bottom: 1px solid var(--border); }
</style>
