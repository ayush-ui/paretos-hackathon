import { useState } from 'react'
import { ChevronDown, Sparkles, UserMinus } from 'lucide-react'
import type { PlanRow, Absence } from '../../api/types'
import { useExplain, useResolveAbsence } from '../../api/hooks'
import { ConfidenceBadge } from '../../components/Badge'
import { CoverageBar } from '../../components/CoverageBar'
import { euro } from '../../lib/format'
import styles from './DayCard.module.css'

// One day in the planner's week: headcount to staff, optimiser's number, coverage, why, savings.
// When absences (from Discord) leave it short, the card turns red and offers a Resolve action.
export function DayCard({ row, absences }: { row: PlanRow; absences: Absence[] }) {
  const [open, setOpen] = useState(false)
  const explain = useExplain(open ? row.date : null)
  const resolve = useResolveAbsence()
  const short = row.coverage === 'short'
  const breach = row.short_by > 2

  const resolveAll = (option: 'filled' | 'accepted') =>
    absences.forEach((a) => resolve.mutate({ id: a.id, date: row.date, option }))

  return (
    <div className={`${styles.card} ${short ? (breach ? styles.breach : styles.warn) : ''}`}>
      <div className={styles.top}>
        <div>
          <div className={styles.weekday}>{row.weekday}</div>
          <div className="caption">{row.date}</div>
        </div>
        <ConfidenceBadge level={row.confidence} />
      </div>

      <div className={styles.figure}>
        <div className={`${styles.count} tabular`}>{row.target_headcount}</div>
        <div className={styles.unit}>
          people
          <span className={styles.optimiser}>optimiser said {row.optimiser_headcount}</span>
        </div>
      </div>

      <CoverageBar confirmed={row.confirmed_headcount} target={row.target_headcount} />

      {short ? (
        <div className={styles.resolve}>
          <div className={styles.shortLine}>
            <UserMinus size={14} strokeWidth={1.5} />
            <span>
              {row.short_by} short · {breach ? 'SLA-breach risk' : 'overtime risk'}{' '}
              <b>{euro(row.sla_risk_eur)}</b>
            </span>
          </div>
          <ul className={styles.absList}>
            {absences.map((a) => (
              <li key={a.id}>
                {a.worker}
                {a.reason ? ` — ${a.reason}` : ''}
              </li>
            ))}
          </ul>
          <div className={styles.actions}>
            <button className={styles.fill} disabled={resolve.isPending} onClick={() => resolveAll('filled')}>
              Fill the gap
            </button>
            <button className={styles.accept} disabled={resolve.isPending} onClick={() => resolveAll('accepted')}>
              Accept gap
            </button>
          </div>
        </div>
      ) : (
        <p className={styles.reason}>{row.reason_short}</p>
      )}

      <div className={styles.footer}>
        <span className={styles.saving}>saves ~{euro(row.est_saving_eur)}</span>
        <button className={styles.why} onClick={() => setOpen((v) => !v)}>
          Why this number <ChevronDown size={14} strokeWidth={1} className={open ? styles.flip : ''} />
        </button>
      </div>

      {open && (
        <div className={styles.detail}>
          {explain.isLoading && <span className="caption">Explaining…</span>}
          {explain.data && (
            <>
              <p>{explain.data.text}</p>
              <div className={styles.basis}>
                {explain.data.llm_used && <Sparkles size={12} strokeWidth={1} />}
                {row.confidence_basis}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
