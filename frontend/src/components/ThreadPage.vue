<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import CommentNode from './CommentNode.vue'

const props = defineProps({ id: Number, authed: Boolean })
const emit = defineEmits(['open-image', 'open-text'])

const data = ref(null)
const missing = ref(false)

async function load() {
  try {
    data.value = await api.thread(props.id)
    missing.value = false
  } catch (e) {
    missing.value = e.status === 404
  }
}

watch(() => props.id, load)
onMounted(() => {
  load()
  window.addEventListener('comments-changed', load)
})
onBeforeUnmount(() => window.removeEventListener('comments-changed', load))
</script>

<template>
  <section class="card">
    <a class="back" href="#/">← Ко всем комментариям</a>
    <p v-if="missing" class="err">Комментарий не найден.</p>
    <CommentNode
      v-else-if="data"
      :comment="data.root"
      :focus="data.focus"
      :authed="authed"
      @changed="load"
      @open-image="emit('open-image', $event)"
      @open-text="emit('open-text', $event)"
    />
  </section>
</template>
