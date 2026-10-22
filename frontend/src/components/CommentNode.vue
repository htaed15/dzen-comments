<script setup>
import { ref } from 'vue'
import CommentForm from './CommentForm.vue'

const props = defineProps({ comment: Object, authed: Boolean, depth: { type: Number, default: 0 } })
const emit = defineEmits(['changed', 'open-image', 'open-text'])
const replying = ref(false)

const fmt = (iso) =>
  new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })

function done() {
  replying.value = false
  emit('changed')
}
</script>

<template>
  <article class="comment" :style="{ '--depth': Math.min(depth, 6) }">
    <header>
      <b>{{ comment.user_name }}</b>
      <a v-if="comment.home_page" :href="comment.home_page" rel="nofollow noopener" target="_blank">
        {{ comment.home_page }}
      </a>
      <time>{{ fmt(comment.created_at) }}</time>
    </header>

    <!-- text уже очищен сервером (белый список тегов) -->
    <div class="body" v-html="comment.text" />

    <div v-for="a in comment.attachments" :key="a.id" class="attachment">
      <span v-if="a.status === 'processing'" class="hint">Обработка файла…</span>
      <span v-else-if="a.status === 'failed'" class="err">Файл не удалось обработать</span>
      <img v-else-if="a.kind === 'image'" :src="a.url" alt="" @click="emit('open-image', a.url)" />
      <button v-else type="button" class="link" @click="emit('open-text', a)">📄 {{ a.name }}</button>
    </div>

    <button type="button" class="link" @click="replying = !replying">Ответить</button>

    <transition name="fade">
      <CommentForm
        v-if="replying"
        :parent-id="comment.id"
        :authed="authed"
        @created="done"
        @cancel="replying = false"
      />
    </transition>

    <CommentNode
      v-for="child in comment.replies"
      :key="child.id"
      :comment="child"
      :authed="authed"
      :depth="depth + 1"
      @changed="emit('changed')"
      @open-image="emit('open-image', $event)"
      @open-text="emit('open-text', $event)"
    />
  </article>
</template>
