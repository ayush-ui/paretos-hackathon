import styles from './CoverageBar.module.css'

// Confirmed vs target headcount. Green when fully covered, red when short (absences will trigger this).
export function CoverageBar({ confirmed, target }: { confirmed: number; target: number }) {
  const pct = target > 0 ? Math.min(100, (confirmed / target) * 100) : 0
  const short = confirmed < target
  return (
    <div className={styles.wrap}>
      <div className={styles.track}>
        <div
          className={`${styles.fill} ${short ? styles.short : styles.ok}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`${styles.label} tabular`}>
        {confirmed}/{target} {short ? `· ${target - confirmed} short` : 'covered'}
      </span>
    </div>
  )
}
