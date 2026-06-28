import { useState } from 'react'
import { Sparkles, Send, CheckCircle2, RotateCcw } from 'lucide-react'
import { useNotePreview, useCommitNote } from '../api/hooks'
import type { NotePreview } from '../api/types'
import { Badge } from './Badge'
import styles from './NoteComposer.module.css'

const PLACEHOLDER =
  'Tell the planner what you saw — be specific. e.g. "Picking felt over-staffed all week; we cleared by 3pm with two fewer pickers. Loading was tight on payday Monday though."'

// Planner speaks her mind → AI structures it → she confirms → it joins the knowledge graph as a candidate.
export function NoteComposer({ compact }: { compact?: boolean }) {
  const [text, setText] = useState('')
  const [author, setAuthor] = useState('')
  const [draft, setDraft] = useState<NotePreview | null>(null)
  const [done, setDone] = useState(false)

  const preview = useNotePreview()
  const commit = useCommitNote()

  const onReview = () => {
    setDone(false)
    preview.mutate(
      { text, author: author || undefined },
      { onSuccess: (d) => setDraft(d) },
    )
  }

  const onConfirm = () => {
    if (!draft) return
    commit.mutate(
      { text, author: author || undefined, parsed: draft.parsed },
      {
        onSuccess: () => {
          setDone(true)
          setDraft(null)
          setText('')
        },
      },
    )
  }

  const reset = () => {
    setDraft(null)
    setDone(false)
  }

  return (
    <div className={`${styles.card} ${compact ? styles.compact : ''}`}>
      <div className={styles.head}>
        <Sparkles size={16} strokeWidth={1.5} color="var(--violet)" />
        <h5>Notice something? Tell the planner.</h5>
      </div>
      <p className="caption">
        Write it in your own words — the AI structures it and adds it to the knowledge the system learns from.
      </p>

      {done && (
        <div className={styles.done}>
          <CheckCircle2 size={16} strokeWidth={1.5} />
          Added to the knowledge graph as a candidate. It&apos;ll be weighed in upcoming plans.
          <button className={styles.link} onClick={() => setDone(false)}>Add another</button>
        </div>
      )}

      {!draft && !done && (
        <>
          <textarea
            className={styles.textarea}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={PLACEHOLDER}
            rows={compact ? 3 : 4}
          />
          <div className={styles.row}>
            <input
              className={styles.author}
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="Your name (optional)"
            />
            <button
              className={styles.review}
              disabled={!text.trim() || preview.isPending}
              onClick={onReview}
            >
              <Sparkles size={14} strokeWidth={1.5} />
              {preview.isPending ? 'Reading your note…' : 'Review with AI'}
            </button>
          </div>
          {preview.isError && <p className={styles.err}>Couldn&apos;t reach the AI. Try again.</p>}
        </>
      )}

      {draft && (
        <div className={styles.review2}>
          <div className={styles.reviewHead}>
            <span className="overline">Here&apos;s how I understood it</span>
            {draft.llm_used && <Badge tone="violet">AI</Badge>}
          </div>
          <p className={styles.summary}>{draft.interpretation.summary}</p>
          <div className={styles.meta}>
            <span><b>Area:</b> {draft.interpretation.scope}</span>
            <span><b>Confidence:</b> {Math.round(draft.interpretation.confidence * 100)}%</span>
            {draft.interpretation.is_one_off && <Badge tone="amber">one-off</Badge>}
          </div>
          <p className={styles.influence}>{draft.interpretation.influence_note}</p>
          <div className={styles.actions}>
            <button className={styles.confirm} disabled={commit.isPending} onClick={onConfirm}>
              <Send size={14} strokeWidth={1.5} />
              {commit.isPending ? 'Adding…' : 'Add to knowledge'}
            </button>
            <button className={styles.edit} onClick={reset}>
              <RotateCcw size={14} strokeWidth={1.5} /> Edit
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
