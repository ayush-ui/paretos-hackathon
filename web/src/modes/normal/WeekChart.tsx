import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import type { PlanRow } from '../../api/types'
import { color, series } from '../../theme/theme'

// Demand (optimiser) vs staffing (plan) headcount across the planned days — the trim, made visible.
export function WeekChart({ rows }: { rows: PlanRow[] }) {
  const data = rows.map((r) => ({
    label: `${r.weekday} ${r.date.slice(5)}`,
    Optimiser: r.optimiser_headcount,
    Plan: r.target_headcount,
  }))
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: -8 }}>
        <CartesianGrid stroke={color.black20} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: color.black40, fontSize: 11 }} interval="preserveStartEnd" />
        <YAxis tick={{ fill: color.black40, fontSize: 11 }} width={36} />
        <Tooltip
          contentStyle={{
            border: `1px solid ${color.black20}`,
            borderRadius: 7,
            fontSize: 12,
            boxShadow: '0 0 10px rgba(0,0,0,0.15)',
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="Optimiser" stroke={series.baseline} strokeWidth={1.5} dot={false} />
        <Line type="monotone" dataKey="Plan" stroke={series.engine} strokeWidth={1.5} dot={{ r: 2 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
