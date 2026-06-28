import { useEffect, useState } from 'react'
import styles from './Loader.module.css'

// Rotating "status" words — they're flavour, not real progress, just so a wait feels alive.
const PHRASES = [
  'Fetching…',
  'Compiling…',
  'Attaching…',
  'Crunching numbers…',
  'Curating beliefs…',
  'Aligning regimes…',
  'Scoring decisions…',
  'Almost there…',
]

function useCyclingPhrase(interval = 1100): string {
  const [i, setI] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setI((x) => (x + 1) % PHRASES.length), interval)
    return () => clearInterval(t)
  }, [interval])
  return PHRASES[i]
}

// Inline spinner — a smooth brand-gradient ring. Use beside small bits of text.
export function Loader({ label, size = 22 }: { label?: string; size?: number }) {
  return (
    <div className={styles.inline} role="status" aria-live="polite">
      <span className={styles.ring} style={{ width: size, height: size }} />
      {label && <span className={styles.label}>{label}</span>}
    </div>
  )
}

// Panel-level loader: an opaque screen with a gradient ring and cycling status text. `label` (if
// given) shows as a quiet subtitle for context; the big line keeps changing on its own.
export function PanelLoader({ label }: { label?: string }) {
  const phrase = useCyclingPhrase()
  return (
    <div className={styles.overlay} role="status" aria-live="polite">
      <div className={styles.inner}>
        <span className={styles.ring} style={{ width: 52, height: 52 }} />
        <span key={phrase} className={styles.phrase}>
          {phrase}
        </span>
        {label && <span className={styles.sub}>{label}</span>}
      </div>
    </div>
  )
}
