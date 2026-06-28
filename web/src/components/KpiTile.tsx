import type { ReactNode } from 'react'
import styles from './KpiTile.module.css'

interface Props {
  label: string
  value: ReactNode
  delta?: ReactNode
  accent?: 'violet' | 'green'
}

export function KpiTile({ label, value, delta, accent }: Props) {
  const accentClass = accent === 'green' ? `${styles.accent} ${styles.accentGreen}` : accent ? styles.accent : ''
  return (
    <div className={`${styles.tile} ${accentClass}`}>
      <div className={styles.label}>{label}</div>
      <div className={`${styles.value} tabular`}>{value}</div>
      {delta && <div className={styles.delta}>{delta}</div>}
    </div>
  )
}
