import { AlertTriangle } from 'lucide-react'
import type { PlanRow } from '../../api/types'
import { euro } from '../../lib/format'
import styles from './AbsenceAlert.module.css'

// Top-of-page banner whenever any day is short of cover (driven by Discord absences).
export function AbsenceAlert({ shortDays }: { shortDays: PlanRow[] }) {
  if (shortDays.length === 0) return null
  const totalRisk = shortDays.reduce((s, r) => s + r.sla_risk_eur, 0)
  const breach = shortDays.some((r) => r.short_by > 2)
  return (
    <div className={`${styles.banner} ${breach ? styles.breach : styles.warn}`}>
      <AlertTriangle size={18} strokeWidth={1.5} />
      <span>
        <b>
          {shortDays.length} day{shortDays.length > 1 ? 's' : ''} short of cover
        </b>{' '}
        ({shortDays.map((r) => `${r.weekday} ${r.short_by} short`).join(', ')}) — expected risk{' '}
        <b>{euro(totalRisk)}</b>. Resolve below.
      </span>
    </div>
  )
}
