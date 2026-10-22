// Клиентская валидация. Сервер проверяет всё то же самое повторно.
const ALLOWED = new Set(['a', 'code', 'i', 'strong'])

export function checkTags(text) {
  const stack = []
  const re = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g
  let m
  while ((m = re.exec(text))) {
    const [, closing, rawName] = m
    const name = rawName.toLowerCase()
    if (!ALLOWED.has(name)) continue
    if (!closing) stack.push(name)
    else if (stack.pop() !== name) return `Неожиданный закрывающий тег </${name}>`
  }
  return stack.length ? `Не закрыт тег <${stack.pop()}>` : ''
}

export function validateForm(f, { authed }) {
  const e = {}
  if (!authed) {
    if (!f.user_name) e.user_name = 'Обязательное поле'
    else if (!/^[A-Za-z0-9]+$/.test(f.user_name)) e.user_name = 'Только латинские буквы и цифры'
    if (!f.email) e.email = 'Обязательное поле'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email)) e.email = 'Неверный формат e-mail'
    if (!f.captcha_answer) e.captcha_answer = 'Введите символы с картинки'
    else if (!/^[A-Za-z0-9]+$/.test(f.captcha_answer)) e.captcha_answer = 'Только латинские буквы и цифры'
  }
  if (f.home_page) {
    try {
      const u = new URL(f.home_page)
      if (!['http:', 'https:'].includes(u.protocol)) throw new Error()
    } catch {
      e.home_page = 'Неверный формат URL'
    }
  }
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
