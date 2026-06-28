import { useState } from 'react'
import { useCurrentPlan, useTrace } from '../../api/hooks'
import { euro, days as fmtDays } from '../../lib/format'
import { Badge } from '../../components/Badge'
import styles from './DecisionTrace.module.css'

// Step-by-step derivation of a single day's number — the auditable "why this number".
export function DecisionTrace() {
  const { data: plan } = useCurrentPlan()
  const [date, setDate] = useState<string | null>(null)
  const active = date ?? plan?.[0]?.date ?? null
  const { data: t } = useTrace(active)

  return (
    <div className={styles.wrap}>
      <div className={styles.picker}>
        <span className="overline">Pick a day</span>
        <div className={styles.chips}>
          {plan?.map((r) => (
            <button
              key={r.date}
              className={`${styles.chip} ${active === r.date ? styles.chipActive : ''}`}
              onClick={() => setDate(r.date)}
            >
              {r.weekday} {r.date.slice(5)}
            </button>
          ))}
        </div>
      </div>

      {t && (
        <div className={styles.trace}>
          <div className={styles.steps}>
            <Step n={1} title="Optimiser recommendation" value={`${fmtDays(t.recommended)} person-days`}
              note="What the existing optimiser proposed." />
            <Step n={2} title="Regime window" value={t.regime_boundary ? `post ${t.regime_boundary}` : 'full history'}
              note="Only recent-regime history is used to calibrate the trim." />
            <Step n={3} title="Trim factor k" value={t.k.toFixed(3)}
              note={`Recent weeks ran at ~${(t.k * 100).toFixed(0)}% of the optimiser.`} />
            <Step n={4} title="Trimmed level" value={`${fmtDays(t.level)} person-days`}
              note="Optimiser × k." />
            <Step n={5} title="Newsvendor offset" value={`+${t.offset.toFixed(2)}`}
              note="Small safety buffer for the asymmetric cost (understaffing is dearer)." />
            <Step n={6} title="Trend lead" value={`${t.trend_adj >= 0 ? '+' : ''}${t.trend_adj.toFixed(2)}`}
              note="Adjustment for the demand trend." />
            <Step n={7} title="Final plan" value={`${fmtDays(t.planned)} person-days`} highlight
              note={`Staff ${Math.round(t.planned)} people.`} />
          </div>

          <div className={styles.outcome}>
            <div className={styles.outcomeHead}>
              {t.is_holdout ? <Badge tone="turq">forecast</Badge> : <Badge tone="violet">known outcome</Badge>}
            </div>
            {t.is_holdout ? (
              <p className="caption">
                October is the withheld holdout — the actual need and cost aren&apos;t revealed (no peeking).
              </p>
            ) : (
              <ul className={styles.kv}>
                <li><span>Actual need</span><b>{fmtDays(t.actual ?? 0)}</b></li>
                <li><span>Our cost</span><b>{euro(t.our_cost ?? 0)}</b></li>
                <li><span>Optimiser cost</span><b>{euro(t.baseline_cost ?? 0)}</b></li>
                <li className={styles.saved}>
                  <span>Saved this day</span><b>{euro((t.baseline_cost ?? 0) - (t.our_cost ?? 0))}</b>
                </li>
              </ul>
            )}
            <p className={styles.reason}>{t.reason_text}</p>
          </div>
        </div>
      )}
    </div>
  )
}

function Step({ n, title, value, note, highlight }: {
  n: number; title: string; value: string; note: string; highlight?: boolean
}) {
  return (
    <div className={`${styles.step} ${highlight ? styles.stepHi : ''}`}>
      <span className={styles.stepN}>{n}</span>
      <div className={styles.stepBody}>
        <div className={styles.stepTop}>
          <span className={styles.stepTitle}>{title}</span>
          <span className={`${styles.stepVal} tabular`}>{value}</span>
        </div>
        <span className={styles.stepNote}>{note}</span>
      </div>
    </div>
  )
}
