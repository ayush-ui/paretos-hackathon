import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import { useCompounding } from '../../api/hooks'
import { color, series } from '../../theme/theme'
import { PanelLoader } from '../../components/Loader'
import styles from './CompoundingTimeline.module.css'

const STATUS_DOT: Record<string, string> = {
  active: color.violet,
  candidate: color.turq,
  retired: color.black40,
}

// The compounding story: cumulative gap-closed rising as knowledge is curated, the cumulative € cost
// of our plan vs the do-nothing baseline pulling apart, plus a lifecycle grid showing each belief
// going candidate → active → retired over the decision weeks.
export function CompoundingTimeline() {
  const { data } = useCompounding()
  if (!data) return <PanelLoader label="Replaying the compounding loop…" />

  const beliefIds = [...new Set(data.flatMap((p) => Object.keys(p.statuses)))].sort()
  const chart = data.map((p) => ({ date: p.decision_date.slice(5), gap: p.cum_gap_pct }))

  // cumulative € cost: our plan vs the baseline (optimiser), accumulated week by week
  let cumPlan = 0
  let cumBase = 0
  const costChart = data.map((p) => {
    cumPlan += p.cycle_cost
    cumBase += p.cycle_baseline
    return {
      date: p.decision_date.slice(5),
      Plan: Math.round(cumPlan),
      Baseline: Math.round(cumBase),
    }
  })

  return (
    <div className={styles.wrap}>
      <div>
        <h5>Cumulative gap closed</h5>
        <p className="caption">Re-curated each week using only what was known then — the system would have won live.</p>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chart} margin={{ top: 8, right: 16, bottom: 0, left: -10 }}>
            <defs>
              <linearGradient id="gap" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color.violet} stopOpacity={0.25} />
                <stop offset="100%" stopColor={color.violet} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={color.black20} strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: color.black40, fontSize: 11 }} />
            <YAxis domain={[85, 95]} tick={{ fill: color.black40, fontSize: 11 }} width={34} unit="%" />
            <Tooltip
              contentStyle={{ border: `1px solid ${color.black20}`, borderRadius: 7, fontSize: 12 }}
              formatter={(v: number) => [`${v}%`, 'gap closed']}
            />
            <Area type="monotone" dataKey="gap" stroke={color.violet} strokeWidth={1.5} fill="url(#gap)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div>
        <h5>Cumulative cost (€)</h5>
        <p className="caption">
          Our plan vs the do-nothing optimiser baseline, accumulated week by week — the widening gap is
          the € the loop saves.
        </p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={costChart} margin={{ top: 8, right: 16, bottom: 0, left: 6 }}>
            <CartesianGrid stroke={color.black20} strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: color.black40, fontSize: 11 }} />
            <YAxis
              tick={{ fill: color.black40, fontSize: 11 }}
              width={52}
              tickFormatter={(v: number) => `€${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip
              contentStyle={{ border: `1px solid ${color.black20}`, borderRadius: 7, fontSize: 12 }}
              formatter={(v: number) => [`€${v.toLocaleString()}`, '']}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="Baseline" stroke={series.baseline} strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="Plan" stroke={series.engine} strokeWidth={1.8} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div>
        <h5>Belief lifecycle</h5>
        <p className="caption">Each cell is a belief&apos;s status at that decision week.</p>
        <div className={styles.gridScroll}>
          <table className={styles.grid}>
            <thead>
              <tr>
                <th className={styles.idcol}>belief</th>
                {data.map((p) => (
                  <th key={p.decision_date} className={styles.wk}>{p.decision_date.slice(5)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {beliefIds.map((id) => (
                <tr key={id}>
                  <td className={styles.idcol}>{id}</td>
                  {data.map((p) => {
                    const s = p.statuses[id]
                    return (
                      <td key={p.decision_date} className={styles.cell}>
                        {s && <span className={styles.dot} style={{ background: STATUS_DOT[s] }} title={s} />}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className={styles.legend}>
          <span><i style={{ background: color.violet }} /> active</span>
          <span><i style={{ background: color.turq }} /> candidate</span>
          <span><i style={{ background: color.black40 }} /> retired</span>
        </div>
      </div>
    </div>
  )
}
