export function formatPopulation(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} млн`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)} тыс`
  return value.toLocaleString('ru-RU')
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return '—'
  return value.toLocaleString('ru-RU')
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

export function formatRate(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${value.toFixed(1)}\u2030`
}
