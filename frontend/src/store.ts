import { defineStore } from 'pinia'
import { api } from './api'

export const useApp = defineStore('app', {
  state: () => ({
    meta: null as any,
    lang: 'en',
    level: 'A1',
    loaded: false,
    toast: null as null | { text: string; kind: string },
  }),
  getters: {
    langInfo: (s) => s.meta?.languages.find((l: any) => l.code === s.lang),
    aiReady: (s) => !!s.meta?.ai,
    phonemeState: (s) => s.meta?.phoneme_engine?.state,
  },
  actions: {
    async load() {
      this.meta = await api.get(`/meta`)
      this.lang = this.meta.settings.lang
      this.meta = await api.get(`/meta?lang=${this.lang}`)
      this.level = this.meta.settings.level
      this.loaded = true
    },
    async save(patch: any) {
      this.meta = await api.put('/settings', patch)
      this.lang = this.meta.settings.lang
      this.level = this.meta.settings.level
    },
    async setLang(code: string) {
      await this.save({ lang: code })
    },
    notify(text: string, kind = 'info') {
      this.toast = { text, kind }
      setTimeout(() => {
        if (this.toast?.text === text) this.toast = null
      }, 4000)
    },
  },
})
