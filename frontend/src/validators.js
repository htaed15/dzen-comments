// Клиентская валидация. Сервер проверяет всё то же самое повторно.
const ALLOWED = new Set(['a', 'code', 'i', 'strong'])

const TAG_RE = /<(\/?)([A-Za-z][A-Za-z0-9]*)((?:\s[^<>]*)?)(\/?)>/g
const ATTR_RE = /^\s+([a-z]+)="([^"<>]*)"/
const HREF_RE = /^https?:\/\/[^\s"<>]+$/
const ATTRS = { a: new Set(['href', 'title']) }

function checkAttrs(tag, raw) {
  const allowed = ATTRS[tag] || new Set()
  const found = {}
  let rest = raw
  while (rest.trim()) {
    const m = ATTR_RE.exec(rest)
    if (!m) return `Тег <${tag}>: атрибуты должны быть в виде имя="значение" в двойных кавычках, в нижнем регистре`
    const [all, key, value] = m
    if (!allowed.has(key)) return `Тег <${tag}>: атрибут ${key} не разрешён`
    if (key in found) return `Тег <${tag}>: атрибут ${key} указан дважды`
    if (!value.trim()) return `Тег <${tag}>: атрибут ${key} не может быть пустым`
    found[key] = value
    rest = rest.slice(all.length)
  }
  if (tag === 'a') {
    if (!('href' in found)) return 'Тег <a> должен содержать атрибут href'
    if (!HREF_RE.test(found.href)) return 'Адрес в href должен начинаться с http:// или https://'
  }
  return ''
}

// Те же правила, что и на сервере (services/sanitizer.py)
export function checkTags(text) {
  const stack = []
  for (const m of text.matchAll(TAG_RE)) {
    const [, closing, rawName, attrs, selfClose] = m
    const tag = rawName.toLowerCase()
    if (!ALLOWED.has(tag)) continue
    if (rawName !== tag) return `Тег <${rawName}> должен быть в нижнем регистре: <${tag}>`
    if (selfClose) return `Тег <${tag}/> должен иметь закрывающий тег </${tag}>`
    if (closing) {
      if (attrs.trim()) return `У закрывающего тега </${tag}> не может быть атрибутов`
      if (stack.pop() !== tag) return `Неожиданный закрывающий тег </${tag}>`
    } else {
      const err = checkAttrs(tag, attrs)
      if (err) return err
      stack.push(tag)
    }
  }
  return stack.length ? `Не закрыт тег <${stack.pop()}>` : ''
}

export function validateForm(f, { authed }) {
  const e = {}
  // поля 1-3 зарегистрированному пользователю подставляются автоматически
  if (!authed) {
    if (!f.user_name) e.user_name = 'Обязательное поле'
    else if (!/^[A-Za-z0-9]+$/.test(f.user_name)) e.user_name = 'Только латинские буквы и цифры'
    if (!f.email) e.email = 'Обязательное поле'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email)) e.email = 'Неверный формат e-mail'
    if (f.home_page) {
      try {
        const u = new URL(f.home_page)
        if (!['http:', 'https:'].includes(u.protocol)) throw new Error()
      } catch {
        e.home_page = 'Неверный формат URL'
      }
    }
  }
  // CAPTCHA нужна всем
  if (!f.captcha_answer) e.captcha_answer = 'Введите символы с картинки'
  else if (!/^[A-Za-z0-9]+$/.test(f.captcha_answer)) e.captcha_answer = 'Только латинские буквы и цифры'
  if (!f.text.trim()) e.text = 'Обязательное поле'
  else {
    const tagError = checkTags(f.text)
    if (tagError) e.text = tagError
  }
  return e
}

export function validateFile(file) {
  if (!file) return ''
  const name = file.name.toLowerCase()
  if (/\.(jpe?g|gif|png)$/.test(name)) return file.size > 5 * 1024 * 1024 ? 'Изображение больше 5 МБ' : ''
  if (name.endsWith('.txt')) return file.size > 100 * 1024 ? 'Текстовый файл больше 100 КБ' : ''
  return 'Допустимы JPG, GIF, PNG или TXT'
}
