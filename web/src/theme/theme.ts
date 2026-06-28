// JS mirror of chart-relevant Cockpit tokens (Recharts/React Flow need JS values, not CSS vars).
// Keep in sync with tokens.css. See docs/DESIGN_SYSTEM.md §3.
export const color = {
  black: '#000000',
  black60: '#666666',
  black40: '#999999',
  black20: '#cccccc',
  silver: '#f2f2f2',
  white: '#ffffff',

  violet: '#5f26e0',
  violet10: '#efe9fc',
  pink: '#f500e1',
  yellow: '#fbb03b',
  dataSlate: '#aaa3cc',

  green: '#00c04d',
  red: '#fb6c4a',
  turq: '#51d7e6',
} as const

// Official categorical chart colorway, in order.
export const chartColorway = [
  '#9F7DED',
  '#96E7F0',
  '#FDA792',
  '#66D994',
  '#FDD089',
  '#999999',
  '#FC896E',
  '#51D7E6',
  '#666666',
  '#33CD71',
] as const

// Series semantics for this app: engine = violet (hero/selection), baseline = grey,
// B2 bar = lavender lead of the colorway, savings = green, warning = yellow.
export const series = {
  engine: color.violet,
  baseline: color.black40,
  b2: chartColorway[0],
  positive: color.green,
  warning: color.yellow,
} as const

// Belief-graph node colour by lifecycle status (violet = active/selected, grey = retired).
export const statusColor: Record<string, string> = {
  active: color.violet,
  candidate: color.dataSlate,
  retired: color.black40,
}

export const brandGradient = 'linear-gradient(45.03deg, #f500e1 0%, #fbb03b 100%)'
