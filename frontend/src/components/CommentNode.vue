<script setup>
import { onMounted, ref } from 'vue'
import { fmtDate } from '../utils'
import Avatar from './Avatar.vue'
import CommentForm from './CommentForm.vue'

const props = defineProps({
  comment: Object,
  authed: Boolean,
  depth: { type: Number, default: 0 },
  focus: { type: Number, default: null },
})
const emit = defineEmits(['changed', 'open-image', 'open-text'])
const replying = ref(false)
const el = ref(null)

function done() {
  replying.value = false
  emit('changed')
}

// Пришли по ссылке на конкретный комментарий: прокручиваем к нему
onMounted(() => {
  if (props.focus === props.comment.id && el.value) {
    el.value.scrollIntoView({ block: 'center' })
  }
})
</script>

<template>
  <article
    :id="'comment-' + comment.id"
    ref="el"
    class="comment"
    :class="{ focused: focus === comment.id }"
    :style="{ '--depth': Math.min(depth, 6) }"
  >
    <header>
      <Avatar :name="comment.user_name" :anonymous="comment.is_anonymous" />
      <a v-if="comment.profile" class="name" :href="'#/u/' + encodeURIComponent(comment.profile)">
        {{ comment.user_name }}
      </a>
      <b v-else class="name anon">{{ comment.user_name }}</b>
      <span v-if="comment.email" class="hint">{{ comment.email }}</span>
      <a v-if="comment.home_page" :href="comment.home_page" rel="nofollow noopener" target="_blank">
        {{ comment.home_page }}
      </a>
      <a class="when" :href="'#/c/' + comment.id" title="Ссылка на комментарий">{{ fmtDate(comment.created_at) }}</a>
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
      :focus="focus"
      @changed="emit('changed')"
      @open-image="emit('open-image', $event)"
      @open-text="emit('open-text', $event)"
    />
  </article>
</template>
