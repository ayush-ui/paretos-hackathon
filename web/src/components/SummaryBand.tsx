import { useSummary } from '../api/hooks'
import { KpiTile } from './KpiTile'
import { euroCompact, euro, pct } from '../lib/format'
import styles from './SummaryBand.module.css'

// End-to-end proof of the API wiring: real numbers from GET /api/summary.
export function SummaryBand() {
  const { data, isLoading, error } = useSummary()

  if (isLoading) return <div className={styles.note}>Loading results…</div>
  if (error || !data) return <div className={styles.note}>Could not load summary.</div>

  const vsB2 = data.engine_gap_closed_pct - data.b2_gap_closed_pct

  return (
    <div className={styles.band}>
      <KpiTile
        label="Saved vs. baseline"
        value={euroCompact(data.saving_vs_baseline_eur)}
        delta={`over ${data.n_days} days`}
        accent="green"
      />
      <KpiTile
        label="Gap closed (engine)"
        value={pct(data.engine_gap_closed_pct)}
        delta={`+${vsB2.toFixed(2)}pp vs. B2 bar`}
        accent="violet"
      />
      <KpiTile label="Engine cost" value={euro(data.engine_cost)} delta={`B2 ${euro(data.b2_adaptive_cost)}`} />
      <KpiTile label="Baseline cost" value={euro(data.baseline_cost)} delta="do-nothing optimiser" />
    </div>
  )
}
