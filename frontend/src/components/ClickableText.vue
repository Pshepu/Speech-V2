<script setup lang="ts">
// Texto en el idioma meta donde cada palabra se puede tocar para traducirla y guardarla.
import { computed, ref } from 'vue'
import { api } from '../api'
import { useApp } from '../store'
import { speak } from '../composables/audio'

const props = defineProps<{ text: string; lang?: string }>()
const app = useApp()
const tokens = computed(() => props.text.split(/(\s+|[.,!?;:"«»()¿¡—])/).filter((t) => t !== ''))
const pop = ref<any>(null)

async function tap(word: string, ev: MouseEvent) {
  if (!/[\p{L}']/u.test(word)) return
  const el = ev.target as HTMLElement
  const rect = el.getBoundingClientRect()
  pop.value = { word, x: rect.left + rect.width / 2, y: rect.bottom + window.scrollY + 6, loading: true, res: null }
  speak(word, { lang: props.lang })
  try {
    pop.value.res = await api.post('/translate', { text: word, lang: props.lang || app.lang, context: props.text })
  } catch (e: any) {
    pop.value.res = { translation: e.message }
  }
  pop.value.loading = false
}

async function save() {
  const p = pop.value
  if (!p?.res) return
  const front = p.res.lemma || p.word
  await api.post('/cards', { lang: props.lang || app.lang, kind: 'word', front, back: p.res.translation, extra: { example: props.text }, source: 'reading' })
  app.notify(`"${front}" añadida a tu repaso`, 'good')
  pop.value = null
}
</script>

<template>
  <span class="ct">
    <span v-for="(t, i) in tokens" :key="i" :class="{ w: /[\p{L}']/u.test(t) }" @click="tap(t, $event)">{{ t }}</span>
  </span>
  <Teleport to="body">
    <div v-if="pop" class="pop-bg" @click="pop = null"></div>
    <div v-if="pop" class="pop card" :style="{ left: pop.x + 'px', top: pop.y + 'px' }">
      <div class="row between"><b>{{ pop.word }}</b><button class="btn sm ghost" @click="pop = null">✕</button></div>
      <div v-if="pop.loading"><span class="spin"></span></div>
      <template v-else-if="pop.res">
        <div>{{ pop.res.translation }}</div>
        <small v-if="pop.res.lemma && pop.res.lemma !== pop.word" class="muted">forma base: {{ pop.res.lemma }}</small>
        <small v-if="pop.res.note" class="muted" style="display:block">{{ pop.res.note }}</small>
        <button class="btn sm primary" style="margin-top:8px" @click="save">+ Añadir a repaso</button>
      </template>
    </div>
  </Teleport>
</template>

<style scoped>
.w { cursor: pointer; border-radius: 4px; }
.w:hover { background: var(--accent-2); color: var(--accent); }
.pop-bg { position: fixed; inset: 0; z-index: 40; }
.pop { position: absolute; transform: translateX(-50%); z-index: 41; min-width: 200px; max-width: 280px; padding: 12px 14px; }
</style>
