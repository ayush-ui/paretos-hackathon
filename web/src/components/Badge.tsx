import type { ReactNode } from 'react'
import styles from './Badge.module.css'

type Tone = 'violet' | 'green' | 'amber' | 'red' | 'turq' | 'neutral'

// Confidence: high = success green, medium = warning amber, low = neutral.
const confidenceTone: Record<string, Tone> = { high: 'green', medium: 'amber', low: 'neutral' }
// Belief lifecycle: active = violet (selection), candidate = turquoise (info), retired = neutral.
const statusTone: Record<string, Tone> = { active: 'violet', candidate: 'turq', retired: 'neutral' }

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`${styles.badge} ${styles[tone]}`}>{children}</span>
}

export function ConfidenceBadge({ level }: { level: 'high' | 'medium' | 'low' }) {
  return (
    <span className={`${styles.badge} ${styles[confidenceTone[level]]}`}>
      <span className={styles.dot} />
      {level[0].toUpperCase() + level.slice(1)}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`${styles.badge} ${styles[statusTone[status] ?? 'neutral']}`}>{status}</span>
}
