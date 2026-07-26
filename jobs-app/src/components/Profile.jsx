import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import Layout from './Layout'

const SENIORITY = [
  { v: 'any', l: 'Any level' },
  { v: 'senior', l: 'Senior and up' },
  { v: 'manager', l: 'Manager and up' },
  { v: 'director', l: 'Director and up' },
  { v: 'vp', l: 'VP and up' },
  { v: 'c_level', l: 'C-level only' },
]

// Array columns are edited as comma-separated text — simplest thing that
// works for lists this short, and it round-trips cleanly.
function toList(s) {
  return String(s || '')
    .split(',')
    .map(x => x.trim())
    .filter(Boolean)
}

export default function Profile() {
  const [p, setP] = useState(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    supabase
      .from('job_profile')
      .select('*')
      .eq('id', 1)
      .single()
      .then(({ data }) => setP(data))
  }, [])

  if (!p) {
    return (
      <Layout>
        <div className="muted">Loading…</div>
      </Layout>
    )
  }

  const set = (k, v) => setP(prev => ({ ...prev, [k]: v }))

  async function save() {
    setSaving(true)
    setMsg('')
    const { error } = await supabase
      .from('job_profile')
      .update({ ...p, updated_at: new Date().toISOString() })
      .eq('id', 1)
    setMsg(error ? error.message : 'Saved. The next scan will use this.')
    setSaving(false)
  }

  return (
    <Layout
      actions={
        <button className="btn" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save profile'}
        </button>
      }
    >
      <header className="page-head">
        <h1>Profile</h1>
        <p className="muted">
          Everything here is fed to the scorer verbatim. The resume field matters most — the
          more specific it is, the more honest the scores and the better the cover letters.
        </p>
      </header>

      {msg && <div className="notice">{msg}</div>}

      <div className="card">
        <label>
          Headline
          <input
            value={p.headline || ''}
            onChange={e => set('headline', e.target.value)}
            placeholder="AI Innovation Leader & Digital Transformation Executive"
          />
        </label>

        <div className="grid-2">
          <label>
            Years of experience
            <input
              type="number"
              value={p.years_experience || ''}
              onChange={e => set('years_experience', e.target.value ? Number(e.target.value) : null)}
            />
          </label>
          <label>
            Based in
            <input
              value={p.location || ''}
              onChange={e => set('location', e.target.value)}
              placeholder="Montreal, QC, Canada"
            />
          </label>
        </div>

        <label>
          Summary
          <textarea
            rows={4}
            value={p.summary || ''}
            onChange={e => set('summary', e.target.value)}
            placeholder="A short positioning statement — who you are and what you're known for."
          />
        </label>
      </div>

      <div className="card">
        <h3>What counts as a good job</h3>

        <label>
          Target titles <span className="muted">— comma separated; these become the search queries</span>
          <input
            value={(p.target_titles || []).join(', ')}
            onChange={e => set('target_titles', toList(e.target.value))}
            placeholder="VP Digital, Head of AI, Director of Digital Product"
          />
        </label>

        <label>
          Target industries <span className="muted">— comma separated</span>
          <input
            value={(p.target_industries || []).join(', ')}
            onChange={e => set('target_industries', toList(e.target.value))}
            placeholder="Telecom, Media, SaaS, Financial services"
          />
        </label>

        <label>
          Locations <span className="muted">— comma separated</span>
          <input
            value={(p.locations || []).join(', ')}
            onChange={e => set('locations', toList(e.target.value))}
            placeholder="Montreal, Canada remote, North America remote"
          />
        </label>

        <div className="grid-2">
          <label>
            Minimum seniority
            <select
              value={p.min_seniority || 'director'}
              onChange={e => set('min_seniority', e.target.value)}
            >
              {SENIORITY.map(s => (
                <option key={s.v} value={s.v}>{s.l}</option>
              ))}
            </select>
          </label>
          <label>
            Compensation floor
            <input
              type="number"
              value={p.min_salary || ''}
              onChange={e => set('min_salary', e.target.value ? Number(e.target.value) : null)}
              placeholder="180000"
            />
          </label>
        </div>

        <label className="check">
          <input
            type="checkbox"
            checked={Boolean(p.remote_ok)}
            onChange={e => set('remote_ok', e.target.checked)}
          />
          Open to fully remote roles
        </label>

        <label>
          Must haves <span className="muted">— comma separated</span>
          <input
            value={(p.must_haves || []).join(', ')}
            onChange={e => set('must_haves', toList(e.target.value))}
            placeholder="Executive scope, AI mandate, real budget ownership"
          />
        </label>

        <label>
          Deal breakers <span className="muted">— comma separated; any match is filtered out before scoring</span>
          <input
            value={(p.deal_breakers || []).join(', ')}
            onChange={e => set('deal_breakers', toList(e.target.value))}
            placeholder="commission only, unpaid, relocation required"
          />
        </label>
      </div>

      <div className="card">
        <h3>Resume</h3>
        <p className="muted">
          Paste your full CV as plain text. This is the single biggest driver of match quality —
          roles, dates, scope, team sizes, and outcomes with numbers all help.
        </p>
        <textarea
          rows={18}
          className="mono"
          value={p.resume_text || ''}
          onChange={e => set('resume_text', e.target.value)}
          placeholder="ROBERT SIMON&#10;Montreal, QC · robert@imetrobert.com · 514-250-8491&#10;&#10;EXPERIENCE&#10;Bell — AI Evangelist & Digital Sales Leader (2024–present)&#10;  · …"
        />
      </div>

      <div className="save-bar">
        <button className="btn" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save profile'}
        </button>
      </div>
    </Layout>
  )
}
