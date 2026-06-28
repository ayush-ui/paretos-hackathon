import styles from './TimeSlider.module.css'

// Scrubs the graph's as_of over the decision weeks. Rightmost = "Now" (end state, as_of=null),
// so you can watch beliefs appear, get superseded, and retire over the season.
export function TimeSlider({
  dates,
  index,
  onChange,
}: {
  dates: string[]
  index: number
  onChange: (i: number) => void
}) {
  const max = dates.length // last position = end state
  const atEnd = index >= max
  const label = atEnd ? 'Now · end state' : `as of ${dates[index]}`
  return (
    <div className={styles.wrap}>
      <div className={styles.headRow}>
        <span className="overline">Time machine</span>
        <span className={styles.label}>{label}</span>
      </div>
      <input
        type="range"
        min={0}
        max={max}
        value={index}
        onChange={(e) => onChange(Number(e.target.value))}
        className={styles.range}
      />
      <div className={styles.ends}>
        <span>{dates[0]}</span>
        <span>now</span>
      </div>
    </div>
  )
}
