import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from 'recharts'
import { useStaffing } from '../../api/hooks'
import { color, series } from '../../theme/theme'
import { PanelLoader } from '../../components/Loader'
import styles from './StaffingPanel.module.css'

// Staffing (operative person-days) per decision week: the optimiser's recommendation, our trimmed
// plan, and the realized actual. The gap between optimiser and actual is the systematic overstaffing
// we trim; our plan tracks the actual far more tightly. October weeks have no actual yet (forecast).
export function StaffingPanel() {
  const { data } = useStaffing()
  if (!data) return <PanelLoader label="Computing staffing over time…" />

  const firstHoldout = data.find((d) => d.is_holdout)?.label
  const chart = data.map((d) => ({
    label: d.label,
    Optimiser: d.optimiser_pd,
    Plan: d.planned_pd,
    Actual: d.actual_pd,
  }))

  return (
    <div className={styles.wrap}>
      <p className={styles.framing}>
        Operative <b>person-days</b> staffed per week. The <b>optimiser</b> systematically overstaffs;
        our <b>plan</b> trims it to track the realized <b>actual</b>. The shaded line marks where the
        October holdout begins — no actuals there yet, so only the plan and optimiser are shown.
      </p>

      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={chart} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid stroke={color.black20} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: color.black40, fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fill: color.black40, fontSize: 11 }} width={42} unit=" pd" />
          <Tooltip
            contentStyle={{ border: `1px solid ${color.black20}`, borderRadius: 7, fontSize: 12 }}
            formatter={(v: number) => [`${v} pd`, '']}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {firstHoldout && (
            <ReferenceLine
              x={firstHoldout}
              stroke={color.violet}
              strokeDasharray="4 3"
              label={{ value: 'holdout →', fill: color.violet, fontSize: 10, position: 'insideTopRight' }}
            />
          )}
          <Line type="monotone" dataKey="Optimiser" stroke={series.baseline} strokeWidth={1.4} dot={false} />
          <Line type="monotone" dataKey="Actual" stroke={color.green} strokeWidth={1.6} dot={{ r: 2 }} connectNulls={false} />
          <Line type="monotone" dataKey="Plan" stroke={series.engine} strokeWidth={1.8} dot={{ r: 2 }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
