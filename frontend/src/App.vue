<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api, getToken } from './api'
import AuthPanel from './components/AuthPanel.vue'
import CommentForm from './components/CommentForm.vue'
import CommentNode from './components/CommentNode.vue'
import Lightbox from './components/Lightbox.vue'

const data = ref({ results: [], count: 0, total_pages: 1 })
const ordering = ref('-created_at') // LIFO по умолчанию
const page = ref(1)
const authed = ref(!!getToken())
const loading = ref(false)
const lightImage = ref('')
const lightText = ref(null)
const liveNote = ref('')

async function load() {
  loading.value = true
  try {
    data.value = await api.list(ordering.value, page.value)
  } finally {
    loading.value = false
  }
}

function sortBy(field) {
  ordering.value = ordering.value === field ? `-${field}` : field
  page.value = 1
  load()
}
const arrow = (field) =>
  ordering.value === field ? '↑' : ordering.value === `-${field}` ? '↓' : ''

function go(p) {
  page.value = Math.min(Math.max(1, p), data.value.total_pages)
  load()
}
const pages = computed(() => Array.from({ length: data.value.total_pages }, (_, i) => i + 1))

// WebSocket: новые комментарии появляются у всех без перезагрузки
let ws
let retry
function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws/comments/`)
  ws.onmessage = (msg) => {
    const ev = JSON.parse(msg.data)
    if (ev.event === 'comment.created') liveNote.value = 'Появились новые комментарии'
    load()
  }
  ws.onclose = () => (retry = setTimeout(connect, 3000))
}
const onExpired = () => (authed.value = false)
onMounted(() => {
  window.addEventListener('auth-expired', onExpired)
  load()
  connect()
})
onBeforeUnmount(() => {
  window.removeEventListener('auth-expired', onExpired)
  clearTimeout(retry)
  if (ws) {
    ws.onclose = null
    ws.close()
  }
})

function created() {
  liveNote.value = ''
  load()
}
</script>

<template>
  <main class="page">
    <header class="top">
      <h1>Комментарии</h1>
      <AuthPanel :authed="authed" @auth="authed = $event" />
    </header>

    <section class="card">
      <h2>Новый комментарий</h2>
      <CommentForm :authed="authed" @created="created" />
    </section>

    <section class="card">
      <div class="sortbar">
        <span>Сортировка:</span>
        <button type="button" @click="sortBy('user_name')">User Name {{ arrow('user_name') }}</button>
        <button type="button" @click="sortBy('email')">E-mail {{ arrow('email') }}</button>
        <button type="button" @click="sortBy('created_at')">Дата {{ arrow('created_at') }}</button>
        <span class="hint">Всего: {{ data.count }}</span>
      </div>

      <p v-if="liveNote" class="note">{{ liveNote }}</p>
      <p v-if="loading && !data.results.length" class="hint">Загрузка…</p>
      <p v-else-if="!data.results.length" class="hint">Пока нет комментариев. Напишите первый.</p>

      <CommentNode
        v-for="c in data.results"
        :key="c.id"
        :comment="c"
        :authed="authed"
        @changed="load"
        @open-image="lightImage = $event"
        @open-text="lightText = $event"
      />

      <nav v-if="data.total_pages > 1" class="pager">
        <button type="button" :disabled="page === 1" @click="go(page - 1)">←</button>
        <button
          v-for="p in pages"
          :key="p"
          type="button"
          :class="{ on: p === page }"
          @click="go(p)"
        >
          {{ p }}
        </button>
        <button type="button" :disabled="page === data.total_pages" @click="go(page + 1)">→</button>
      </nav>
    </section>

    <Lightbox
      :image="lightImage"
      :text-file="lightText"
      @close="(lightImage = ''), (lightText = null)"
    />
  </main>
</template>
