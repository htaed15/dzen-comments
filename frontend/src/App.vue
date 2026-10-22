<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api, getToken } from './api'
import { fmtDate } from './utils'
import Avatar from './components/Avatar.vue'
import AuthPanel from './components/AuthPanel.vue'
import CommentForm from './components/CommentForm.vue'
import CommentNode from './components/CommentNode.vue'
import Lightbox from './components/Lightbox.vue'
import ProfilePage from './components/ProfilePage.vue'
import ThreadPage from './components/ThreadPage.vue'

// Простая маршрутизация по hash: #/ (список), #/u/<имя> (профиль), #/c/<id> (ветка)
function parseRoute(hash) {
  const profile = hash.match(/^#\/u\/([^/?]+)/)
  if (profile) return { name: 'profile', username: decodeURIComponent(profile[1]) }
  const thread = hash.match(/^#\/c\/(\d+)/)
  if (thread) return { name: 'thread', id: Number(thread[1]) }
  return { name: 'home' }
}
const route = ref(parseRoute(location.hash))
const onHash = () => {
  route.value = parseRoute(location.hash)
  window.scrollTo(0, 0)
}

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

const ariaSort = (field) =>
  ordering.value === field ? 'ascending' : ordering.value === `-${field}` ? 'descending' : 'none'

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
    if (route.value.name === 'home') {
      if (ev.event === 'comment.created') liveNote.value = 'Появились новые комментарии'
      load()
    }
    window.dispatchEvent(new Event('comments-changed')) // обновит ветку или профиль
  }
  ws.onclose = () => (retry = setTimeout(connect, 3000))
}

const onExpired = () => (authed.value = false)
onMounted(() => {
  window.addEventListener('hashchange', onHash)
  window.addEventListener('auth-expired', onExpired)
  load()
  connect()
})
onBeforeUnmount(() => {
  window.removeEventListener('hashchange', onHash)
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
      <h1><a class="home-link" href="#/">Комментарии</a></h1>
      <AuthPanel :authed="authed" @auth="authed = $event" />
    </header>

    <ProfilePage v-if="route.name === 'profile'" :username="route.username" />
    <ThreadPage
      v-else-if="route.name === 'thread'"
      :id="route.id"
      :authed="authed"
      @open-image="lightImage = $event"
      @open-text="lightText = $event"
    />

    <template v-else>
      <section class="card">
        <h2>Новый комментарий</h2>
        <CommentForm :authed="authed" @created="created" />
      </section>

      <section class="card">
        <div class="sortbar"><span class="hint">Всего: {{ data.count }}</span></div>

        <p v-if="liveNote" class="note">{{ liveNote }}</p>
        <p v-if="loading && !data.results.length" class="hint">Загрузка…</p>
        <p v-else-if="!data.results.length" class="hint">Пока нет комментариев. Напишите первый.</p>

        <table v-if="data.results.length" class="ctable">
          <thead>
            <tr>
              <th :aria-sort="ariaSort('user_name')">
                <button type="button" @click="sortBy('user_name')">User Name {{ arrow('user_name') }}</button>
              </th>
              <th :aria-sort="ariaSort('email')">
                <button type="button" @click="sortBy('email')">E-mail {{ arrow('email') }}</button>
              </th>
              <th :aria-sort="ariaSort('created_at')">
                <button type="button" @click="sortBy('created_at')">Дата {{ arrow('created_at') }}</button>
              </th>
            </tr>
          </thead>
          <tbody v-for="c in data.results" :key="c.id">
            <tr class="meta">
              <td>
               <div class="who">
                <Avatar :name="c.user_name" :anonymous="c.is_anonymous" />
                <a v-if="c.profile" class="name" :href="'#/u/' + encodeURIComponent(c.profile)">{{ c.user_name }}</a>
                <b v-else class="name anon">{{ c.user_name }}</b>
                <a v-if="c.home_page" class="site" :href="c.home_page" rel="nofollow noopener" target="_blank">{{ c.home_page }}</a>
               </div>
              </td>
              <td class="mail">{{ c.email || '—' }}</td>
              <td class="when-cell">
                <a class="when" :href="'#/c/' + c.id" title="Ссылка на комментарий">{{ fmtDate(c.created_at) }}</a>
              </td>
            </tr>
            <tr class="content">
              <td colspan="3">
                <CommentNode
                  bare
                  :comment="c"
                  :authed="authed"
                  @changed="load"
                  @open-image="lightImage = $event"
                  @open-text="lightText = $event"
                />
              </td>
            </tr>
          </tbody>
        </table>

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
    </template>

    <Lightbox
      :image="lightImage"
      :text-file="lightText"
      @close="(lightImage = ''), (lightText = null)"
    />
  </main>
</template>
