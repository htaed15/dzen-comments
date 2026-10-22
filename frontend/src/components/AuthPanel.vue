<script setup>
import { reactive, ref } from 'vue'
import { api, flattenErrors, setToken } from '../api'

defineProps({ authed: Boolean })
const emit = defineEmits(['auth'])

const open = ref(false)
const mode = ref('login')
const f = reactive({ username: '', email: '', password: '' })
const errors = ref({})

function checkPassword(value) {
  if (value.length < 6) return 'Пароль должен быть не короче 6 символов'
  if (!/\p{L}/u.test(value) || !/\d/.test(value)) return 'Пароль должен содержать и буквы, и цифры'
  return ''
}

async function go() {
  errors.value = {}
  if (mode.value === 'register') {
    const problem = checkPassword(f.password)
    if (problem) {
      errors.value = { password: problem }
      return
    }
  }
  try {
    const data =
      mode.value === 'login'
        ? await api.login({ username: f.username, password: f.password })
        : await api.register({ ...f })
    setToken(data.access)
    open.value = false
    emit('auth', true)
  } catch (e) {
    errors.value = flattenErrors(e.data)
  }
}
function logout() {
  setToken('')
  emit('auth', false)
}
</script>

<template>
  <div class="auth">
    <template v-if="authed">
      <span class="hint">Вы вошли, CAPTCHA не нужна</span>
      <button type="button" @click="logout">Выйти</button>
    </template>
    <template v-else>
      <button type="button" @click="open = !open">Войти / регистрация</button>
      <form v-if="open" class="auth-box" @submit.prevent="go">
        <div class="toolbar">
          <button type="button" :class="{ on: mode === 'login' }" @click="mode = 'login'">Вход</button>
          <button type="button" :class="{ on: mode === 'register' }" @click="mode = 'register'">Регистрация</button>
        </div>
        <input v-model.trim="f.username" placeholder="Логин (латиница, цифры)" />
        <input v-if="mode === 'register'" v-model.trim="f.email" type="email" placeholder="E-mail" />
        <input v-model="f.password" type="password" :placeholder="mode === 'register' ? 'Пароль (от 6 символов, буквы и цифры)' : 'Пароль'" />
        <small v-for="(msg, key) in errors" :key="key" class="err">{{ msg }}</small>
        <button class="primary" type="submit">{{ mode === 'login' ? 'Войти' : 'Создать аккаунт' }}</button>
      </form>
    </template>
  </div>
</template>
