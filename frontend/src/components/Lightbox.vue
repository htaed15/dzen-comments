<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({ image: String, textFile: Object })
const emit = defineEmits(['close'])
const content = ref('')

watch(
  () => props.textFile,
  async (file) => {
    content.value = ''
    if (!file) return
    const resp = await fetch(file.url)
    content.value = await resp.text() // выводится как текст, не как HTML
  },
  { immediate: true },
)

const onKey = (e) => e.key === 'Escape' && emit('close')
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <transition name="lb">
    <div v-if="image || textFile" class="lightbox" @click.self="emit('close')">
      <div class="lightbox-box">
        <button type="button" class="close" aria-label="Закрыть" @click="emit('close')">×</button>
        <img v-if="image" :src="image" alt="" />
        <template v-else>
          <h4>{{ textFile.name }}</h4>
          <pre>{{ content }}</pre>
        </template>
      </div>
    </div>
  </transition>
</template>
