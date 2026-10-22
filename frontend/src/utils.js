const COLORS = ['#e57373', '#64b5f6', '#81c784', '#ffb74d', '#9575cd', '#4db6ac', '#f06292', '#a1887f']

export function initials(name) {
  return (name || '?').slice(0, 2).toUpperCase()
}

export function avatarColor(name) {
  let h = 0
  for (const ch of name || '') h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return COLORS[h % COLORS.length]
}

// 22.05.22 в 22:30
export function fmtDate(iso) {
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${String(d.getFullYear()).slice(2)} в ${p(d.getHours())}:${p(d.getMinutes())}`
}
