<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useApp } from './store'
import { NAV } from './router'
import Onboarding from './components/Onboarding.vue'

const app = useApp()
const error = ref('')

onMounted(async () => {
  try {
    await app.load()
  } catch (e: any) {
    error.value = 'No se pudo conectar con el servidor. ¿Está en marcha?'
  }
  try {
    const t = localStorage.getItem('theme')
    if (t) document.documentElement.dataset.theme = t
  } catch {}
})

async function changeLang(e: Event) {
  await app.setLang((e.target as HTMLSelectElement).value)
  location.reload()
}
</script>

<template>
  <div v-if="error" class="main"><div class="card empty">{{ error }}</div></div>
  <div v-else-if="app.loaded" class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="logo">🎙️</div> Speech</div>
      <select class="lang-select" :value="app.lang" @change="changeLang">
        <option v-for="l in app.meta.languages" :key="l.code" :value="l.code">{{ l.flag }} {{ l.name }}</option>
      </select>
      <router-link v-for="n in NAV" :key="n.path" :to="n.path" class="nav-link">
        <span class="ic">{{ n.icon }}</span>{{ n.name }}
      </router-link>
      <div class="spacer"></div>
      <router-link to="/metodo" class="nav-link"><span class="ic">🧭</span>El método</router-link>
      <router-link to="/ajustes" class="nav-link"><span class="ic">⚙️</span>Ajustes</router-link>
    </aside>
    <header class="topbar">
      <div class="brand" style="padding:0"><div class="logo">🎙️</div> Speech</div>
      <div class="row">
        <select class="lang-select sm" :value="app.lang" @change="changeLang">
          <option v-for="l in app.meta.languages" :key="l.code" :value="l.code">{{ l.flag }}</option>
        </select>
        <router-link to="/ajustes" class="btn icon ghost">⚙️</router-link>
      </div>
    </header>
    <main class="main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in"><component :is="Component" :key="$route.fullPath.split('?')[0]" /></transition>
      </router-view>
    </main>
    <nav class="bottom-nav">
      <router-link v-for="n in NAV.slice(0, 6)" :key="n.path" :to="n.path"><span class="ic">{{ n.icon }}</span>{{ n.name }}</router-link>
    </nav>
    <Onboarding v-if="!app.meta.settings.onboarded" />
  </div>
  <div v-else class="main"><div class="empty"><span class="spin"></span> Cargando…</div></div>
  <transition name="fade">
    <div v-if="app.toast" class="toast" :class="app.toast.kind">{{ app.toast.text }}</div>
  </transition>
</template>

<style scoped>
.lang-select { margin: 0 4px 12px; width: auto; font-weight: 600; }
.lang-select.sm { margin: 0; padding: 5px 8px; }
</style>
