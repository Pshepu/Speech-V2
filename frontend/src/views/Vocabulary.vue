<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import PlayButton from '../components/PlayButton.vue'

const app = useApp()
const data = ref<any>(null)
const q = ref('')
const level = ref('')
const category = ref('')
const offset = ref(0)
const LIMIT = 100
let t: any = null

async function load() {
  const p = new URLSearchParams({ lang: app.lang, limit: String(LIMIT), offset: String(offset.value) })
  if (q.value) p.set('q', q.value)
  if (level.value) p.set('level', level.value)
  if (category.value) p.set('category', category.value)
  data.value = await api.get(`/vocab?${p}`)
}
onMounted(load)
watch(q, () => { clearTimeout(t); t = setTimeout(() => { offset.value = 0; load() }, 250) })
watch([level, category], () => { offset.value = 0; load() })

async function add(w: any) {
  await api.post('/cards', { lang: app.lang, kind: 'word', front: w.word, back: w.translation, extra: { example: w.example, example_es: w.example_es, pos: w.pos, level: w.level }, source: 'vocab' })
  w.in_deck = true
}
async function addAllVisible() {
  for (const w of data.value.words.filter((w: any) => !w.in_deck).slice(0, 30)) await add(w)
  app.notify('Palabras añadidas a tu repaso', 'good')
}
</script>

<template>
  <div>
    <div class="page-head">
      <div><h1>📚 Vocabulario</h1><p>Las palabras ordenadas por frecuencia real de uso: las primeras 2.000 cubren la gran mayoría de lo que oirás.</p></div>
    </div>
    <div class="card flat filters">
      <input type="text" v-model="q" placeholder="🔎 Buscar en el idioma o en español…" />
      <select v-model="level"><option value="">Todos los niveles</option><option v-for="l in ['A1','A2','B1','B2']" :key="l">{{ l }}</option></select>
      <select v-model="category"><option value="">Todas las categorías</option><option v-for="c in data?.categories || []" :key="c">{{ c }}</option></select>
    </div>
    <div v-if="data && !data.total" class="card empty">
      Aún no hay vocabulario para este idioma. Ejecuta <code>python scripts/build_content.py</code> para generarlo.
    </div>
    <div v-else-if="data" class="card" style="margin-top:16px">
      <div class="row between" style="margin-bottom:10px">
        <small class="muted">{{ data.total }} palabras</small>
        <button class="btn sm" @click="addAllVisible">+ Añadir las visibles (máx. 30)</button>
      </div>
      <div class="list">
        <div v-for="w in data.words" :key="w.word" class="item">
          <div class="rank">#{{ w.rank }}</div>
          <div class="w">
            <div class="row"><b>{{ w.word }}</b><PlayButton :text="w.word" /><small class="muted">{{ w.pos }}</small><span class="chip">{{ w.level }}</span></div>
            <div>{{ w.translation }}</div>
            <small class="muted" v-if="w.example">{{ w.example }} — {{ w.example_es }}</small>
          </div>
          <button class="btn sm" :class="w.known ? 'good' : ''" :disabled="w.in_deck" @click="add(w)">{{ w.known ? '✓ Sabida' : w.in_deck ? '✓ En repaso' : '+ Repaso' }}</button>
        </div>
      </div>
      <div class="row" style="justify-content:center;margin-top:14px" v-if="data.total > LIMIT">
        <button class="btn sm" :disabled="offset === 0" @click="offset -= LIMIT; load()">← Anterior</button>
        <small class="muted">{{ offset + 1 }}–{{ Math.min(offset + LIMIT, data.total) }}</small>
        <button class="btn sm" :disabled="offset + LIMIT >= data.total" @click="offset += LIMIT; load()">Siguiente →</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filters { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 10px; }
@media (max-width: 700px) { .filters { grid-template-columns: 1fr; } }
.item { display: flex; gap: 12px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border); }
.rank { width: 46px; color: var(--muted); font-size: .8rem; font-family: var(--mono); }
.w { flex: 1; min-width: 0; }
</style>
