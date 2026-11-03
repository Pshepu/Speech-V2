<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ value: number; size?: number; label?: string }>(), { size: 96 })
const r = 42
const c = 2 * Math.PI * r
const cls = computed(() => (props.value >= 80 ? 'good' : props.value >= 60 ? 'mid' : 'bad'))
</script>

<template>
  <div class="ring" :style="{ width: size + 'px', height: size + 'px' }">
    <svg viewBox="0 0 100 100">
      <circle cx="50" cy="50" :r="r" class="track" />
      <circle cx="50" cy="50" :r="r" class="val" :class="cls" :stroke-dasharray="c" :stroke-dashoffset="c * (1 - Math.max(0, Math.min(100, value)) / 100)" />
    </svg>
    <div class="txt"><b :class="'score-' + cls">{{ Math.round(value) }}</b><small v-if="label">{{ label }}</small></div>
  </div>
</template>

<style scoped>
.ring { position: relative; flex: none; }
svg { transform: rotate(-90deg); width: 100%; height: 100%; }
circle { fill: none; stroke-width: 9; stroke-linecap: round; }
.track { stroke: var(--surface-2); }
.val { transition: stroke-dashoffset .8s ease; }
.val.good { stroke: var(--good); } .val.mid { stroke: var(--warn); } .val.bad { stroke: var(--bad); }
.txt { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; line-height: 1.1; }
.txt b { font-size: 1.6em; }
.txt small { font-size: .7rem; color: var(--muted); }
</style>
