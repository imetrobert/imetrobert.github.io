import { useState } from 'react'
import { supabase } from '../lib/supabase'

const STATUSES = ['interested', 'applied', 'interviewing', 'offer', 'rejected', 'passed']

function money(job) {
  if (!job.salary_min && !job.salary_max) return null
  const fmt = n => (n ? Math.round(n).toLocaleString() : '?')
  return `${fmt(job.salary_min)}–${fmt(job.salary_max)} ${job.salary_currency || ''}`.trim()
}

function download(filename, text) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// The scorer writes "moderate: <reasoning>" — pull the level off the front so
// it can be colour-coded, and fall back to neutral if the shape varies.
function riskLevel(text) {
  const m = String(text || '').match(/^\s*(none|low|moderate|high)\b/i)
  return m ? m[1].toLowerCase() : 'unknown'
}

function slug(s) {
  return String(s || 'role').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50)
}

export default function JobCard({ job, onChanged }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [docs, setDocs] = useState(null)
  const [err, setErr] = useState('')

  async function setStatus(status) {
    await supabase.from('job_applications').upsert(
      { posting_id: job.id, status, updated_at: new Date().toISOString() },
      { onConflict: 'posting_id' }
    )
    onChanged?.()
  }

  async function generate() {
    setBusy(true)
    setErr('')
    try {
      const { data, error } = await supabase.functions.invoke('generate-application', {
        body: { posting_id: job.id },
      })
      if (error) throw error
      if (data?.error) throw new Error(data.error)
      setDocs(data)
      onChanged?.()
    } catch (e) {
      setErr(e.message || 'Generation failed')
    }
    setBusy(false)
  }

  async function loadExisting() {
    const { data } = await supabase
      .from('job_applications')
      .select('cover_letter, tailored_cv')
      .eq('posting_id', job.id)
      .maybeSingle()
    if (data?.cover_letter) setDocs({ cover_letter: data.cover_letter, tailored_cv: data.tailored_cv })
  }

  function toggle() {
    const next = !open
    setOpen(next)
    if (next && !docs && job.has_cover_letter) loadExisting()
  }

  const pay = money(job)

  return (
    <article className={`job ${open ? 'open' : ''}`}>
      <button className="job-head" onClick={toggle}>
        <span className={`score tier-${job.tier}`}>{job.score}</span>
        <span className="job-title">
          <strong>{job.title}</strong>
          <span className="job-meta">
            {job.company || 'Unknown company'}
            {job.location ? ` · ${job.location}` : ''}
            {job.remote ? ' · Remote' : ''}
            {pay ? ` · ${pay}` : ''}
          </span>
        </span>
        <span className="job-tags">
          {job.app_status && job.app_status !== 'interested' && (
            <span className="tag status">{job.app_status}</span>
          )}
          <span className={`tag tier-${job.tier}`}>{job.tier}</span>
        </span>
      </button>

      {open && (
        <div className="job-body">
          {job.why_fit && (
            <section>
              <h4>Why this fits you</h4>
              <p>{job.why_fit}</p>
            </section>
          )}
          {job.gaps && (
            <section>
              <h4>The honest gaps</h4>
              <p className="muted">{job.gaps}</p>
            </section>
          )}
          {job.overqualification_risk && (
            <section>
              <h4>Screening risk</h4>
              <p className={`risk risk-${riskLevel(job.overqualification_risk)}`}>
                {job.overqualification_risk}
              </p>
            </section>
          )}
          {job.pitch_angle && (
            <section>
              <h4>Lead with</h4>
              <p className="pitch">{job.pitch_angle}</p>
            </section>
          )}

          <div className="job-actions">
            {job.url && (
              <a className="btn ghost" href={job.url} target="_blank" rel="noreferrer">
                View posting ↗
              </a>
            )}
            <button className="btn" onClick={generate} disabled={busy}>
              {busy ? 'Drafting…' : docs ? 'Regenerate' : 'Draft cover letter + CV'}
            </button>
            <select
              value={job.app_status || 'interested'}
              onChange={e => setStatus(e.target.value)}
            >
              {STATUSES.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {err && <div className="err">{err}</div>}

          {docs && (
            <div className="docs">
              <section>
                <div className="doc-head">
                  <h4>Cover letter</h4>
                  <button
                    className="btn ghost sm"
                    onClick={() =>
                      download(`cover-letter-${slug(job.company)}-${slug(job.title)}.txt`, docs.cover_letter)
                    }
                  >
                    Download
                  </button>
                </div>
                <pre className="doc">{docs.cover_letter}</pre>
              </section>
              {docs.tailored_cv && (
                <section>
                  <div className="doc-head">
                    <h4>Tailored CV</h4>
                    <button
                      className="btn ghost sm"
                      onClick={() =>
                        download(`cv-${slug(job.company)}-${slug(job.title)}.md`, docs.tailored_cv)
                      }
                    >
                      Download
                    </button>
                  </div>
                  <pre className="doc">{docs.tailored_cv}</pre>
                </section>
              )}
              <p className="muted sm">
                Drafts, not final copy — read them before sending. Every factual claim should be
                one you can stand behind in an interview.
              </p>
            </div>
          )}
        </div>
      )}
    </article>
  )
}
