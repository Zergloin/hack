export function getPopulationColor(population: number): string {
  if (population >= 1_000_000) return '#1a365d'
  if (population >= 500_000) return '#2b6cb0'
  if (population >= 200_000) return '#3182ce'
  if (population >= 100_000) return '#4299e1'
  if (population >= 50_000) return '#63b3ed'
  if (population >= 20_000) return '#90cdf4'
  return '#bee3f8'
}

export function getGrowthColor(percent: number): string {
  if (percent >= 10) return '#22543d'
  if (percent >= 5) return '#276749'
  if (percent >= 1) return '#38a169'
  if (percent >= 0) return '#68d391'
  if (percent >= -1) return '#fc8181'
  if (percent >= -5) return '#e53e3e'
  if (percent >= -10) return '#c53030'
  return '#9b2c2c'
}

export const CHART_COLORS = [
  '#2b6cb0',
  '#38a169',
  '#d69e2e',
  '#e53e3e',
  '#805ad5',
  '#319795',
  '#dd6b20',
  '#3182ce',
]
