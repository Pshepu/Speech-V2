import { createRouter, createWebHistory } from 'vue-router'

export const NAV = [
  { path: '/', name: 'Hoy', icon: '🏠' },
  { path: '/misiones', name: 'Misiones', icon: '🕹️' },
  { path: '/pronunciacion', name: 'Pronunciación', icon: '🎙️' },
  { path: '/oido', name: 'Escucha', icon: '👂' },
  { path: '/repaso', name: 'Repaso', icon: '🧠' },
  { path: '/gramatica', name: 'Gramática', icon: '📐' },
  { path: '/lectura', name: 'Lectura', icon: '📖' },
  { path: '/vocabulario', name: 'Vocabulario', icon: '📚' },
  { path: '/fluidez', name: 'Fluidez', icon: '⚡' },
  { path: '/nivel', name: 'Mi nivel', icon: '🎯' },
  { path: '/progreso', name: 'Progreso', icon: '📈' },
]

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/', component: () => import('./views/Home.vue') },
    { path: '/misiones', component: () => import('./views/Missions.vue') },
    { path: '/mision/:runId', component: () => import('./views/MissionRun.vue') },
    { path: '/pronunciacion', component: () => import('./views/Pronunciation.vue') },
    { path: '/oido', component: () => import('./views/Listening.vue') },
    { path: '/repaso', component: () => import('./views/Review.vue') },
    { path: '/gramatica', component: () => import('./views/Grammar.vue') },
    { path: '/gramatica/:id', component: () => import('./views/Lesson.vue') },
    { path: '/escritura', component: () => import('./views/Writing.vue') },
    { path: '/lectura', component: () => import('./views/Reading.vue') },
    { path: '/vocabulario', component: () => import('./views/Vocabulary.vue') },
    { path: '/fluidez', component: () => import('./views/Fluency.vue') },
    { path: '/progreso', component: () => import('./views/Progress.vue') },
    { path: '/nivel', component: () => import('./views/Level.vue') },
    { path: '/ajustes', component: () => import('./views/Settings.vue') },
    { path: '/metodo', component: () => import('./views/Method.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
