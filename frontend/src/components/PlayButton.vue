<script setup lang="ts">
import { speak, speaking } from '../composables/audio'
const props = defineProps<{ text: string; lang?: string; voice?: string; rate?: number; random?: boolean; label?: string; size?: string }>()
function play() { speak(props.text, { lang: props.lang, voice: props.voice, rate: props.rate, random: props.random }) }
</script>

<template>
  <button class="btn" :class="[size || 'sm', label ? '' : 'icon ghost']" :title="label || 'Escuchar'" @click.stop="play">
    <span v-if="speaking === text.trim()" class="spin"></span><span v-else>{{ rate && rate < 0 ? '🐢' : '🔊' }}</span>
    <span v-if="label">{{ label }}</span>
  </button>
</template>
