<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api, flattenErrors, getToken } from '../api'
import { validateFile, validateForm } from '../validators'

const props = defineProps({ parentId: { type: Number, default: null }, authed: Boolean })
const emit = defineEmits(['created', 'cancel'])

const form = reactive({ user_name: '', email: '', home_page: '', text: '', captcha_answer: '' })
const file = ref(null)
const errors = ref({})
const captcha = reactive({ key: '', image: '' })
const previewHtml = ref('')
const busy = ref(false)
const textarea = ref(null)
const fileInput = ref(null)

const showIdentity = computed(() => !props.authed)

async function loadCaptcha() {
  const data = await api.captcha()
  captcha.key = data.key
  captcha.image = data.image
  form.captcha_answer = ''
}
onMounted(() => { if (showIdentity.value) loadCaptcha() })
// после выхода из аккаунта форма снова просит имя и CAPTCHA
watch(showIdentity, (visible) => { if (visible) loadCaptcha() })

// Панель тегов: оборачивает выделенный текст
function wrap(tag) {
  const el = textarea.value
  const start = el.selectionStart
  const end = el.selectionEnd
  const selected = form.text.slice(start, end)
  let open = `<${tag}>`
  if (tag === 'a') {
    const href = prompt('Ссылка (http:// или https://)', 'https://')
    if (!href) return
    open = `<a href="${href.replace(/"/g, '')}" title="">`
  }
  form.text = form.text.slice(0, start) + open + selected + `</${tag}>` + form.text.slice(end)
  requestAnimationFrame(() => {
    el.focus()
    const pos = start + open.length + selected.length
    el.setSelectionRange(pos, pos)
  })
}

async function preview() {
  errors.value = {}
  try {
    previewHtml.value = (await api.preview(form.text)).html
  } catch (e) {
    previewHtml.value = ''
    errors.value = flattenErrors(e.data)
  }
}

function onFile(ev) {
  const picked = ev.target.files[0] || null
  const problem = validateFile(picked)
  if (problem) {
    errors.value = { ...errors.value, file: problem }
    ev.target.value = ''
    file.value = null
    return
  }
  const { file: _drop, ...rest } = errors.value
  errors.value = rest
  file.value = picked
}

async function submit() {
  errors.value = validateForm(form, { authed: props.authed })
  const fileProblem = validateFile(file.value)
  if (fileProblem) errors.value.file = fileProblem
  if (Object.keys(errors.value).length) return

  const body = new FormData()
  body.append('text', form.text)
  if (props.parentId) body.append('parent', props.parentId)
  if (showIdentity.value) {
    body.append('user_name', form.user_name)
    body.append('email', form.email)
    if (form.home_page) body.append('home_page', form.home_page)
    body.append('captcha_key', captcha.key)
    body.append('captcha_answer', form.captcha_answer)
  }
  if (file.value) body.append('file', file.value)

  busy.value = true
  try {
    await api.create(body)
    form.text = ''
    previewHtml.value = ''
    file.value = null
    if (fileInput.value) fileInput.value.value = ''
    emit('created')
  } catch (e) {
    errors.value = flattenErrors(e.data)
  } finally {
    busy.value = false
    if (showIdentity.value) loadCaptcha()
  }
}
</script>

<template>
  <form class="form" novalidate @submit.prevent="submit">
    <div v-if="showIdentity" class="grid">
      <label>
        User Name *
        <input v-model.trim="form.user_name" maxlength="50" autocomplete="nickname" />
        <small v-if="errors.user_name" class="err">{{ errors.user_name }}</small>
      </label>
      <label>
        E-mail *
        <input v-model.trim="form.email" type="email" autocomplete="email" />
        <small v-if="errors.email" class="err">{{ errors.email }}</small>
      </label>
      <label>
        Home page
        <input v-model.trim="form.home_page" placeholder="https://" />
        <small v-if="errors.home_page" class="err">{{ errors.home_page }}</small>
      </label>
    </div>

    <div class="toolbar">
      <button type="button" @click="wrap('i')">[i]</button>
      <button type="button" @click="wrap('strong')">[strong]</button>
      <button type="button" @click="wrap('code')">[code]</button>
      <button type="button" @click="wrap('a')">[a]</button>
    </div>
    <textarea ref="textarea" v-model="form.text" rows="4" placeholder="Текст сообщения *" />
    <small v-if="errors.text" class="err">{{ errors.text }}</small>

    <div class="row">
      <input ref="fileInput" type="file" accept=".jpg,.jpeg,.gif,.png,.txt" @change="onFile" />
      <small class="hint">Картинка JPG/GIF/PNG (уменьшится до 320×240) или TXT до 100 КБ</small>
    </div>
    <small v-if="errors.file" class="err">{{ errors.file }}</small>

    <div v-if="showIdentity" class="captcha">
      <img v-if="captcha.image" :src="captcha.image" alt="CAPTCHA" />
      <button type="button" class="link" @click="loadCaptcha">Обновить</button>
      <input v-model.trim="form.captcha_answer" maxlength="8" placeholder="Символы с картинки *" />
      <small v-if="errors.captcha_answer" class="err">{{ errors.captcha_answer }}</small>
    </div>

    <div class="actions">
      <button type="submit" class="primary" :disabled="busy">Отправить</button>
      <button type="button" @click="preview">Предпросмотр</button>
      <button v-if="parentId" type="button" @click="emit('cancel')">Отмена</button>
    </div>

    <transition name="fade">
      <div v-if="previewHtml" class="preview">
        <strong>Предпросмотр</strong>
        <div class="body" v-html="previewHtml" />
      </div>
    </transition>
  </form>
</template>
