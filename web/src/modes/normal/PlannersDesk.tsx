import { useMemo, useState } from 'react'
import { Card } from '../../components/Card'
import { useCurrentPlan, useAbsences } from '../../api/hooks'
import type { PlanRow, Absence } from '../../api/types'
import { AboutPanel } from './AboutPanel'
import { AbsenceAlert } from './AbsenceAlert'
import { TrackRecord } from './TrackRecord'
import { WeekChart } from './WeekChart'
import { DayCard } from './DayCard'
import { ReportAbsence } from './ReportAbsence'
import { NoteComposer } from '../../components/NoteComposer'
import { PanelLoader } from '../../components/Loader'
import styles from './PlannersDesk.module.css'

// Group plan rows into the weeks a planner actually rosters (one decision cycle = one week).
function groupByWeek(rows: PlanRow[]) {
  const map = new Map<string, PlanRow[]>()
  for (const r of rows) {
    const list = map.get(r.decision_date) ?? []
    list.push(r)
    map.set(r.decision_date, list)
  }
  return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
}

// Open absences for a given date (a 'filled' resolution restores cover; 'accepted' keeps the gap).
function openAbsencesFor(date: string, absences: Absence[]): Absence[] {
  return absences.filter((a) => a.date === date && (a.status === 'open' || a.resolution === 'accepted'))
}

export function PlannersDesk() {
  const { data: plan, isLoading, error } = useCurrentPlan()
  const { data: absences = [] } = useAbsences()
  const weeks = useMemo(() => (plan ? groupByWeek(plan) : []), [plan])
  const [weekIdx, setWeekIdx] = useState(0)

  if (isLoading) return <PanelLoader label="Loading this week's plan…" />
  if (error || !plan) return <p className="caption">Could not load the plan.</p>

  const safeIdx = Math.min(weekIdx, weeks.length - 1)
  const [decisionDate, days] = weeks[safeIdx]
  const weekTotal = days.reduce((s, r) => s + r.target_headcount, 0)
  const weekSaving = days.reduce((s, r) => s + r.est_saving_eur, 0)
  const shortDays = days.filter((r) => r.coverage === 'short')

  return (
    <div className={styles.wrap}>
      <header className={styles.head}>
        <div>
          <h3>Planner&apos;s desk</h3>
          <p className="caption">How many operatives to roster each day, and why.</p>
        </div>
        <div className={styles.weekPicker}>
          {weeks.map(([dd], i) => (
            <button
              key={dd}
              className={`${styles.weekBtn} ${i === safeIdx ? styles.weekActive : ''}`}
              onClick={() => setWeekIdx(i)}
            >
              Week {i + 1}
            </button>
          ))}
        </div>
      </header>

      <AboutPanel />
      <AbsenceAlert shortDays={shortDays} />
      <TrackRecord />

      <Card>
        <div className={styles.weekStat}>
          <div>
            <span className="caption">Week of {decisionDate} · planned</span>
            <div className={`${styles.bigNum} tabular`}>{weekTotal} person-days</div>
          </div>
          <div className={styles.saveBadge}>saves ~€{weekSaving.toLocaleString()}</div>
        </div>
        <WeekChart rows={days} />
      </Card>

      <div className={styles.grid}>
        {days.map((r) => (
          <DayCard key={r.date} row={r} absences={openAbsencesFor(r.date, absences)} />
        ))}
      </div>

      {/* Operational: log an absence against this week's roster; the day's coverage updates live. */}
      <ReportAbsence days={days} />

      {/* Planner can capture an observation right from the desk; it joins the graph as a candidate. */}
      <NoteComposer compact />
    </div>
  )
}
