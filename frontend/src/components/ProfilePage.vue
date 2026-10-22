<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { fmtDate } from '../utils'
import Avatar from './Avatar.vue'

const props = defineProps({ username: String })

const data = ref(null)
const page = ref(1)
const missing = ref(false)

async function load() {
  try {
    data.value = await api.profile(props.username, page.value)
    missing.value = false
  } catch (e) {
    data.value = null
    missing.value = e.status === 404
  }
}

watch(
  () => props.username,
  () => {
    page.value = 1
    load()
  },
)
onMounted(() => {
  load()
  window.addEventListener('comments-changed', load)
})
onBeforeUnmount(() => window.removeEventListener('comments-changed', load))

function go(p) {
  page.value = p
  load()
}
const pages = computed(() => Array.from({ length: data.value?.total_pages || 1 }, (_, i) => i + 1))
</script>

<template>
  <section class="card">
    <a class="back" href="#/">← Ко всем комментариям</a>

    <p v-if="missing" class="err">Пользователь не найден.</p>

    <template v-else-if="data">
      <div class="profile-head">
        <Avatar :name="data.profile.username" :size="56" />
        <div>
          <h2>{{ data.profile.username }}</h2>
          <p class="hint">
            {{ data.profile.registered ? 'Зарегистрирован' : 'Без регистрации' }}
            · с {{ fmtDate(data.profile.joined) }}
            · комментариев: {{ data.count }}
          </p>
          <a v-if="data.profile.home_page" :href="data.profile.home_page" rel="nofollow noopener" target="_blank">
            {{ data.profile.home_page }}
          </a>
        </div>
      </div>

      <p v-if="!data.results.length" class="hint">Публичных комментариев пока нет.</p>

      <article v-for="c in data.results" :key="c.id" class="profile-comment">
        <header>
          <span class="hint">{{ c.is_reply ? 'Ответ' : 'Комментарий' }} · {{ fmtDate(c.created_at) }}</span>
          <a :href="'#/c/' + c.id">Открыть ветку</a>
        </header>
        <div class="body" v-html="c.text" />
      </article>

      <nav v-if="data.total_pages > 1" class="pager">
        <button v-for="p in pages" :key="p" type="button" :class="{ on: p === page }" @click="go(p)">
          {{ p }}
        </button>
      </nav>
    </template>
  </section>
</template>
