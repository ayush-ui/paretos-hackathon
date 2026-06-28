import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
} from 'recharts'
import { useSynthetic } from '../../api/hooks'
import { color, series } from '../../theme/theme'
import { PanelLoader } from '../../components/Loader'
import styles from './SyntheticPanel.module.css'

// SYNTHETIC robustness: alternative Octobers the single real holdout can't show. The engine should
// beat the no-knowledge ablation where the regime is learnable (ramp, pick-by-light) and is honestly
// neutral/worse on pure unseen shocks (heat/flu). Labelled synthetic; the real-data ablation is primary.
export function SyntheticPanel() {
  const { data } = useSynthetic()
  if (!data) return <PanelLoader label="Running the synthetic stress-test…" />

  const chart = data.worlds.map((w) => ({
    world: w.world,
    engine: Math.round(w.engine_gap_pct * 10) / 10,
    ablation: Math.round(w.naive_gap_pct * 10) / 10,
    beats: w.engine_beats_naive,
  }))

  return (
    <div className={styles.wrap}>
      <div className={styles.synthBadge}>SYNTHETIC — what-if regimes, not the scored holdout</div>
      <p className={styles.framing}>{data.note}</p>

      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chart} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
          <CartesianGrid stroke={color.black20} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="world" tick={{ fill: color.black40, fontSize: 11 }} interval={0} />
          <YAxis tick={{ fill: color.black40, fontSize: 11 }} width={38} unit="%" />
          <Tooltip
            contentStyle={{ border: `1px solid ${color.black20}`, borderRadius: 7, fontSize: 12 }}
            formatter={(v: number, name: string) => [`${v}%`, name]}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="ablation" name="no-knowledge ablation" fill={series.baseline} radius={[3, 3, 0, 0]} />
          <Bar dataKey="engine" name="our engine" radius={[3, 3, 0, 0]}>
            {chart.map((d) => (
              <Cell key={d.world} fill={d.beats ? series.engine : color.yellow} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Regime world</th>
            <th>Engine</th>
            <th>Ablation</th>
            <th>Verdict</th>
            <th>What it stresses</th>
          </tr>
        </thead>
        <tbody>
          {data.worlds.map((w) => (
            <tr key={w.world}>
              <td>{w.world}</td>
              <td className={styles.num}>{w.engine_gap_pct.toFixed(1)}%</td>
              <td className={styles.num}>{w.naive_gap_pct.toFixed(1)}%</td>
              <td>
                <span className={w.engine_beats_naive ? styles.win : styles.tie}>
                  {w.engine_beats_naive ? 'knowledge helps' : 'unseen shock'}
                </span>
              </td>
              <td className="caption">{w.story}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
