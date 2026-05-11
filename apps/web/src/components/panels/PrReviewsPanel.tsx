import { useEffect, useState } from 'react'
import {
  completePullRequestReview,
  createPullRequestReview,
  importReviewFeedbackFromFindings,
  listPullRequestReviews,
} from '../../api'
import type {
  PullRequestReview,
  PullRequestReviewConclusion,
} from '../../types'

export function PullRequestReviewsPanel({
  prDraftId,
  onFeedbackImported,
}: {
  prDraftId: string
  onFeedbackImported?: () => void
}) {
  const [open, setOpen] = useState(false)
  const [reviews, setReviews] = useState<PullRequestReview[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manualOpen, setManualOpen] = useState(false)
  const [manualSummary, setManualSummary] = useState('')
  const [manualRaw, setManualRaw] = useState('')
  const [manualConclusion, setManualConclusion] = useState<PullRequestReviewConclusion>('comment_only')

  async function refresh() {
    setBusy(true)
    setError(null)
    try {
      setReviews(await listPullRequestReviews(prDraftId))
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (open) {
      refresh()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, prDraftId])

  async function prepare() {
    setBusy(true)
    setError(null)
    try {
      await createPullRequestReview(prDraftId, { provider: 'kody', mode: 'prepare' })
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function recordManual() {
    setBusy(true)
    setError(null)
    try {
      await createPullRequestReview(prDraftId, {
        provider: 'kody',
        mode: 'manual',
        summary: manualSummary,
        raw_output: manualRaw,
        conclusion: manualConclusion,
      })
      setManualOpen(false)
      setManualSummary('')
      setManualRaw('')
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function importFindings(reviewId: string) {
    setBusy(true)
    setError(null)
    try {
      const resp = await importReviewFeedbackFromFindings(reviewId)
      setError(`Imported ${resp.created} feedback item(s); skipped ${resp.skipped} duplicate(s).`)
      onFeedbackImported?.()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function markComplete(reviewId: string, conclusion: PullRequestReviewConclusion) {
    setBusy(true)
    setError(null)
    try {
      await completePullRequestReview(reviewId, { conclusion })
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ marginTop: 8, borderTop: '1px solid #222', paddingTop: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', fontSize: 11 }}
      >
        {open ? '▾' : '▸'} Kody reviews{reviews.length ? ` (${reviews.length})` : ''}
      </button>
      {open && (
        <div style={{ marginTop: 6 }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button onClick={prepare} disabled={busy} style={{ fontSize: 11 }}>
              Prepare Kody review package
            </button>
            <button onClick={() => setManualOpen(o => !o)} disabled={busy} style={{ fontSize: 11 }}>
              {manualOpen ? 'Cancel manual' : 'Record manual Kody result'}
            </button>
            <button onClick={refresh} disabled={busy} style={{ fontSize: 11 }}>
              Refresh
            </button>
          </div>
          {error && <div style={{ color: '#f88', fontSize: 11, marginTop: 4 }}>{error}</div>}
          {manualOpen && (
            <div style={{ marginTop: 6, padding: 6, border: '1px solid #333', borderRadius: 3 }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
                <label style={{ fontSize: 11 }}>Conclusion:
                  <select
                    value={manualConclusion}
                    onChange={e => setManualConclusion(e.target.value as PullRequestReviewConclusion)}
                    style={{ marginLeft: 4, fontSize: 11, background: '#1a1a1a', color: '#fff', border: '1px solid #444' }}
                  >
                    <option value="approved">approved</option>
                    <option value="changes_requested">changes_requested</option>
                    <option value="comment_only">comment_only</option>
                    <option value="failed">failed</option>
                    <option value="skipped">skipped</option>
                    <option value="requires_human_review">requires_human_review</option>
                  </select>
                </label>
              </div>
              <textarea
                value={manualSummary}
                onChange={e => setManualSummary(e.target.value)}
                placeholder="Summary"
                style={{ width: '100%', minHeight: 40, fontSize: 11, background: '#1a1a1a', color: '#fff', border: '1px solid #444', borderRadius: 3, padding: 4, marginBottom: 4 }}
              />
              <textarea
                value={manualRaw}
                onChange={e => setManualRaw(e.target.value)}
                placeholder="Pasted Kody output (optional)"
                style={{ width: '100%', minHeight: 60, fontSize: 11, background: '#1a1a1a', color: '#fff', border: '1px solid #444', borderRadius: 3, padding: 4 }}
              />
              <button onClick={recordManual} disabled={busy} style={{ fontSize: 11, marginTop: 4 }}>
                Save
              </button>
            </div>
          )}
          {reviews.length === 0 ? (
            <div style={{ fontSize: 11, color: '#888', marginTop: 6 }}>No reviews yet.</div>
          ) : (
            <div style={{ marginTop: 6 }}>
              {reviews.map(r => (
                <PullRequestReviewCard
                  key={r.id}
                  review={r}
                  busy={busy}
                  onMarkComplete={c => markComplete(r.id, c)}
                  onImportFindings={() => importFindings(r.id)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function PullRequestReviewCard({
  review,
  busy,
  onMarkComplete,
  onImportFindings,
}: {
  review: PullRequestReview
  busy: boolean
  onMarkComplete: (c: PullRequestReviewConclusion) => void
  onImportFindings: () => void
}) {
  const [conclusion, setConclusion] = useState<PullRequestReviewConclusion>('approved')
  return (
    <div style={{ border: '1px solid #2a2a2a', borderRadius: 3, padding: 6, marginBottom: 6 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="status" style={{ fontSize: 10 }}>{review.provider}</span>
        <span className="status" style={{ fontSize: 10 }}>{review.status}</span>
        {review.conclusion && (
          <span className="status" style={{ fontSize: 10 }}>{review.conclusion}</span>
        )}
        <span style={{ fontSize: 10, color: '#888' }}>{new Date(review.created_at).toLocaleString()}</span>
      </div>
      {review.summary && (
        <div style={{ fontSize: 11, marginTop: 4 }}>{review.summary}</div>
      )}
      {review.findings.length > 0 && (
        <>
          <ul style={{ fontSize: 11, marginTop: 4, paddingLeft: 16 }}>
            {review.findings.map((f, i) => (
              <li key={i}>
                {f.severity ? `[${f.severity}] ` : ''}
                {f.category ? `(${f.category}) ` : ''}
                {f.message}
                {f.file_path ? ` — ${f.file_path}${f.line ? `:${f.line}` : ''}` : ''}
              </li>
            ))}
          </ul>
          <div style={{ marginTop: 4 }}>
            <button
              type="button"
              onClick={onImportFindings}
              disabled={busy}
              style={{ fontSize: 11 }}
              title="Create ReviewFeedback rows from these findings (idempotent)."
            >
              Import findings as feedback
            </button>
          </div>
        </>
      )}
      {review.external_review_url && (
        <div style={{ fontSize: 11, marginTop: 4 }}>
          <a href={review.external_review_url} target="_blank" rel="noreferrer">External review</a>
        </div>
      )}
      {review.status !== 'completed' && review.status !== 'cancelled' && (
        <div style={{ marginTop: 4, display: 'flex', gap: 6, alignItems: 'center' }}>
          <select
            value={conclusion}
            onChange={e => setConclusion(e.target.value as PullRequestReviewConclusion)}
            style={{ fontSize: 11, background: '#1a1a1a', color: '#fff', border: '1px solid #444' }}
          >
            <option value="approved">approved</option>
            <option value="changes_requested">changes_requested</option>
            <option value="comment_only">comment_only</option>
            <option value="failed">failed</option>
            <option value="skipped">skipped</option>
            <option value="requires_human_review">requires_human_review</option>
          </select>
          <button onClick={() => onMarkComplete(conclusion)} disabled={busy} style={{ fontSize: 11 }}>
            Mark complete
          </button>
        </div>
      )}
    </div>
  )
}
