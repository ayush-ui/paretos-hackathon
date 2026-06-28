import { useState } from 'react'
import { UserMinus, Send, CheckCircle2 } from 'lucide-react'
import { useCreateAbsence } from '../../api/hooks'
import type { PlanRow, AbsenceImpact } from '../../api/types'
import { euro } from '../../lib/format'
import styles from './ReportAbsence.module.css'

// Report an absence straight from the desk — same operational path as the Discord bot. Lowering a day's
// confirmed headcount turns it short and surfaces the € risk from the real asymmetric cost model.
export function ReportAbsence({ days }: { days: PlanRow[] }) {
  const [date, setDate] = useState(days[0]?.date ?? '')
  const [worker, setWorker] = useState('')
  const [reason, setReason] = useState('')
  const [impact, setImpact] = useState<AbsenceImpact | null>(null)

  const create = useCreateAbsence()

  const onSubmit = () => {
    if (!date || !worker.trim()) return
    create.mutate(
      { worker: worker.trim(), date, reason: reason.trim() || undefined },
      {
        onSuccess: (d) => {
          setImpact(d)
          setWorker('')
          setReason('')
        },
      },
    )
  }

  const tone = impact?.sla_breach ? styles.breach : impact?.short_by ? styles.warn : styles.ok

  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <UserMinus size={16} strokeWidth={1.5} color="var(--red)" />
        <h5>Someone out? Report an absence.</h5>
      </div>
      <p className="caption">
        Logs against the live roster and recomputes that day&apos;s coverage — the same loop the Discord bot drives.
      </p>

      <div className={styles.fields}>
        <select className={styles.select} value={date} onChange={(e) => setDate(e.target.value)}>
          {days.map((r) => (
            <option key={r.date} value={r.date}>
              {r.weekday} · {r.date}
            </option>
          ))}
        </select>
        <input
          className={styles.input}
          value={worker}
          onChange={(e) => setWorker(e.target.value)}
          placeholder="Who's out? (name)"
        />
      </div>
      <div className={styles.fields}>
        <input
          className={styles.input}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason (optional, e.g. sick)"
        />
        <button
          className={styles.submit}
          disabled={!date || !worker.trim() || create.isPending}
          onClick={onSubmit}
        >
          <Send size={14} strokeWidth={1.5} />
          {create.isPending ? 'Logging…' : 'Report absence'}
        </button>
      </div>

      {create.isError && <p className={styles.err}>Couldn&apos;t log that absence. Try again.</p>}

      {impact && (
        <div className={`${styles.impact} ${tone}`}>
          <CheckCircle2 size={16} strokeWidth={1.5} />
          <div>
            <p className={styles.impactMsg}>{impact.message}</p>
            <p className={styles.impactMeta}>
              Coverage {impact.confirmed_headcount}/{impact.target_headcount}
              {impact.short_by > 0 && <> · risk {euro(impact.sla_risk_eur)}</>}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
