import { useState } from 'react'
import { Info, X } from 'lucide-react'
import styles from './AboutPanel.module.css'

// Plain-English explainer so a first-time planner understands what the plan is and how to read it.
export function AboutPanel() {
  const [open, setOpen] = useState(true)
  if (!open)
    return (
      <button className={styles.reopen} onClick={() => setOpen(true)}>
        <Info size={16} strokeWidth={1} /> How to read this plan
      </button>
    )
  return (
    <div className={styles.panel}>
      <button className={styles.close} onClick={() => setOpen(false)} aria-label="Dismiss">
        <X size={16} strokeWidth={1} />
      </button>
      <p className="overline">How to read this plan</p>
      <p className={styles.body}>
        Each card is one working day. <b>Staff N people</b> is how many operatives to roster — already
        trimmed from what the old optimiser suggested, which reliably over-staffs. The engine learns the
        optimiser&apos;s weekly error and cuts the excess while keeping enough cover, so you spend less
        without risking the workload. The green bar shows you have everyone you need; if someone reports
        out, it turns red and flags the gap. Open <b>&ldquo;Why this number&rdquo;</b> for the reasoning
        on any day.
      </p>
    </div>
  )
}
