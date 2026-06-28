import { useSummary } from '../../api/hooks'
import { euroCompact, pct } from '../../lib/format'
import styles from './TrackRecord.module.css'

// One honest line of proof the trimming works — from the walk-forward backtest.
export function TrackRecord() {
  const { data } = useSummary()
  if (!data) return null
  return (
    <div className={styles.strip}>
      <span className={styles.dot} />
      <span>
        Track record: over {data.n_days} past working days this plan would have saved{' '}
        <b>{euroCompact(data.saving_vs_baseline_eur)}</b> vs. running the optimiser as-is —{' '}
        <b>{pct(data.engine_gap_closed_pct)}</b> of the avoidable cost, tested walk-forward.
      </span>
    </div>
  )
}
