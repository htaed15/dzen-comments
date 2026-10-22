<script setup>
import { computed } from 'vue'
import { avatarColor, initials } from '../utils'

const props = defineProps({ name: String, anonymous: Boolean, size: { type: Number, default: 28 } })
const style = computed(() => ({
  width: props.size + 'px',
  height: props.size + 'px',
  fontSize: Math.round(props.size * 0.4) + 'px',
  background: props.anonymous ? '#b7bccd' : avatarColor(props.name),
}))
</script>

<template>
  <span class="avatar" :style="style" aria-hidden="true">{{ anonymous ? '?' : initials(name) }}</span>
</template>
