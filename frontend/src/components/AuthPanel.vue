<script setup>
import { reactive, ref, watch } from 'vue'
import { api, flattenErrors, setToken, setTokens } from '../api'

const props = defineProps({ authed: Boolean })
const emit = defineEmits(['auth'])

const open = ref(false)
const mode = ref('login')
const f = reactive({ username: '', email: '', password: '' })
const errors = ref({})
const myName = ref('')

async function loadMe() {
  try {
    myName.value = (await api.me()).username
  } catch {
    myName.value = ''
  }
}
watch(() => props.authed, (v) => (v ? loadMe() : (myName.value = '')), { immediate: true })

function checkPassword(value) {
  if (value.length < 6) return 'Пароль должен быть не короче 6 символов'
  if (!/\p{L}/u.test(value) || !/\d/.test(value)) return 'Пароль должен содержать и буквы, и цифры'
  return ''
}

async function go() {
  errors.value = {}
  if (mode.value === 'register') {
    const local = {}
    if (!/^[A-Za-z0-9]+$/.test(f.username)) local.username = 'Только латинские буквы и цифры'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email)) local.email = 'Неверный формат e-mail'
    const pw = checkPassword(f.password)
    if (pw) local.password = pw
    if (Object.keys(local).length) {
      errors.value = local
      return
    }
  }
  try {
    let data
    if (mode.value === 'login') {
      data = await api.login({ username: f.username, password: f.password })
    } else {
      // Home page создаётся при регистрации автоматически — это ссылка на профиль
      const home = `${location.origin}/#/u/${encodeURIComponent(f.username)}`
      const body = { username: f.username, email: f.email, password: f.password, home_page: home }
      data = await api.register(body)
    }
    setTokens(data.access, data.refresh)
    open.value = false
    f.password = ''
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
      <a v-if="myName" :href="'#/u/' + encodeURIComponent(myName)">Мой профиль ({{ myName }})</a>
      <button type="button" @click="logout">Выйти</button>
    </template>
    <template v-else>
      <button type="button" @click="open = !open">Войти / регистрация</button>
      <form v-if="open" class="auth-box" @submit.prevent="go">
        <div class="toolbar">
          <button type="button" :class="{ on: mode === 'login' }" @click="mode = 'login'; errors = {}">Вход</button>
          <button type="button" :class="{ on: mode === 'register' }" @click="mode = 'register'; errors = {}">Регистрация</button>
        </div>
        <input v-model.trim="f.username" placeholder="User Name (латиница, цифры)" />
        <input v-if="mode === 'register'" v-model.trim="f.email" type="email" placeholder="E-mail" />
        <input
          v-model="f.password"
          type="password"
          :placeholder="mode === 'register' ? 'Пароль (от 6 символов, буквы и цифры)' : 'Пароль'"
        />
        <small v-for="(msg, key) in errors" :key="key" class="err">{{ msg }}</small>
        <button class="primary" type="submit">{{ mode === 'login' ? 'Войти' : 'Создать аккаунт' }}</button>
      </form>
    </template>
  </div>
</template>
