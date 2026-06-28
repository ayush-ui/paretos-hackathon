// Single source for number formatting (€ + person-days). Use everywhere for consistency.
const eur0 = new Intl.NumberFormat('en-IE', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

export const euro = (v: number) => eur0.format(v)

// Compact € for large savings, e.g. €218.3k.
export const euroCompact = (v: number) => {
  if (Math.abs(v) >= 1000) return `€${(v / 1000).toFixed(1)}k`
  return euro(v)
}

export const pct = (v: number, digits = 1) => `${v.toFixed(digits)}%`

// Person-days: one decimal, the unit the submission is scored on.
export const days = (v: number) => v.toFixed(1)

export const round0 = (v: number) => Math.round(v).toString()
