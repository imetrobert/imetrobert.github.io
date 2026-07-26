// Match scoring: how well does one posting fit the profile, and why.

import { generateJSON } from './llm.js'

// Structured-output schema. Note the deliberate absence of numeric
// minimum/maximum — the Claude structured-outputs validator rejects those —
// so the 0..100 bound is enforced in clampScore() below instead.
const SCORE_SCHEMA = {
  type: 'object',
  properties: {
    score: {
      type: 'integer',
      description: '0-100. How strong a candidate is this person for this specific role?',
    },
    tier: {
      type: 'string',
      enum: ['exceptional', 'strong', 'possible', 'stretch', 'poor'],
    },
    why_fit: {
      type: 'string',
      description:
        'Two to four sentences, addressed to the candidate as "you", naming the specific experience that maps to this role. Concrete, not flattering.',
    },
    gaps: {
      type: 'string',
      description:
        'The honest case against — what the role wants that the candidate lacks, or where they would be stretched. Empty string only if genuinely none.',
    },
    pitch_angle: {
      type: 'string',
      description:
        'One sentence: the single strongest angle to lead with in a cover letter for this role.',
    },
  },
  required: ['score', 'tier', 'why_fit', 'gaps', 'pitch_angle'],
  additionalProperties: false,
}

const SENIORITY_RANK = {
  any: 0,
  senior: 1,
  manager: 2,
  director: 3,
  vp: 4,
  c_level: 5,
}

// Rough seniority read from the title. Used only to skip obviously-junior
// postings before spending an LLM call — never to reject on its own when the
// signal is ambiguous (unknown → keep, let the model judge).
export function titleSeniority(title = '') {
  const t = title.toLowerCase()
  if (/\b(chief|cto|cio|cmo|ceo|coo|cdo|caio|c-level)\b/.test(t)) return 'c_level'
  if (/\b(vp|vice[- ]president|svp|evp|head of)\b/.test(t)) return 'vp'
  if (/\b(director|dir\.)\b/.test(t)) return 'director'
  // "Lead" and "Principal" are deliberately NOT bucketed here: their scope
  // swings from senior-IC to director depending on the company, and guessing
  // wrong silently drops good roles. Left unknown so the model judges them.
  if (/\b(manager|mgr)\b/.test(t)) return 'manager'
  if (/\b(senior|sr\.?|staff)\b/.test(t)) return 'senior'
  if (/\b(junior|jr\.?|intern|internship|entry[- ]level|co[- ]op|graduate|apprentice|assistant|coordinator|associate|analyst i\b|technician)\b/.test(t)) {
    return 'junior'
  }
  return 'unknown'
}

// Cheap gate ahead of the LLM. Returns a reason string when the posting
// should be skipped, or null to score it.
export function prefilterReason(profile, posting) {
  const min = SENIORITY_RANK[profile.min_seniority ?? 'director'] ?? 3
  const seen = titleSeniority(posting.title)

  if (seen === 'junior' && min > 0) return 'below seniority floor'
  if (seen !== 'unknown' && SENIORITY_RANK[seen] !== undefined && SENIORITY_RANK[seen] < min) {
    return 'below seniority floor'
  }

  for (const bad of profile.deal_breakers || []) {
    const needle = String(bad).trim().toLowerCase()
    if (!needle) continue
    if (`${posting.title} ${posting.company} ${posting.description}`.toLowerCase().includes(needle)) {
      return `deal-breaker: ${bad}`
    }
  }

  // Geography: only reject when the posting is clearly non-remote AND names a
  // country the profile doesn't cover. Vague locations pass through.
  if (!posting.remote && posting.location) {
    const loc = posting.location.toLowerCase()
    const wanted = (profile.locations || []).map(l => l.toLowerCase())
    const coversCanada = wanted.some(l => /canada|montr|quebec|qc|toronto|ontario|remote/.test(l))
    const coversUS = wanted.some(l => /united states|usa|u\.s\.|north america|remote/.test(l))
    const looksUS = /\b(usa|united states|, [a-z]{2}$|california|texas|new york|florida)\b/.test(loc)
    const looksCanada = /canada|montr|quebec|qc|toronto|ontario|vancouver|calgary|ottawa|bc|alberta/.test(loc)
    if (looksCanada && !coversCanada) return 'location not targeted'
    if (looksUS && !looksCanada && !coversUS) return 'location not targeted'
  }

  return null
}

function clampScore(n) {
  const v = Math.round(Number(n))
  if (!Number.isFinite(v)) return 0
  return Math.max(0, Math.min(100, v))
}

function profileBlock(p) {
  const lines = [
    p.headline && `Headline: ${p.headline}`,
    p.years_experience && `Years of experience: ${p.years_experience}`,
    p.location && `Based in: ${p.location}`,
    p.summary && `Summary: ${p.summary}`,
    p.target_titles?.length && `Target roles: ${p.target_titles.join('; ')}`,
    p.target_industries?.length && `Preferred industries: ${p.target_industries.join('; ')}`,
    p.locations?.length && `Acceptable locations: ${p.locations.join('; ')}`,
    p.remote_ok ? 'Open to fully remote work.' : 'Prefers on-site or hybrid.',
    p.min_salary && `Compensation floor: ${p.min_salary} ${p.salary_currency || 'CAD'}`,
    p.must_haves?.length && `Must have: ${p.must_haves.join('; ')}`,
    p.deal_breakers?.length && `Deal breakers: ${p.deal_breakers.join('; ')}`,
  ].filter(Boolean)

  let out = lines.join('\n')
  if (p.resume_text) out += `\n\n--- RESUME ---\n${p.resume_text}`
  return out
}

function postingBlock(job) {
  const salary =
    job.salary_min || job.salary_max
      ? `Salary: ${job.salary_min ?? '?'}–${job.salary_max ?? '?'} ${job.salary_currency || ''}`
      : null
  return [
    `Title: ${job.title}`,
    job.company && `Company: ${job.company}`,
    job.location && `Location: ${job.location}`,
    job.remote ? 'Remote: yes' : null,
    salary,
    '',
    // Descriptions from aggregators can be long; the tail is usually boilerplate
    // (EEO statements, benefits) that adds tokens without adding signal.
    (job.description || '').slice(0, 6000),
  ]
    .filter(Boolean)
    .join('\n')
}

const SYSTEM = `You are an experienced executive recruiter assessing whether one specific candidate should apply to one specific job.

Be calibrated and honest. This assessment is read only by the candidate, and its usefulness depends entirely on it being trustworthy — a list where everything scores 85 is worthless. Most postings are a mediocre fit; say so. Reserve high scores for roles where this candidate would genuinely be a leading applicant.

Scoring guide:
  90-100 exceptional - the role reads as though it were written for them
  75-89  strong      - clearly qualified, would likely get an interview
  55-74  possible    - plausible fit, but they are one of many candidates
  35-54  stretch     - missing something material; a long shot
  0-34   poor        - wrong level, wrong field, or wrong location

Judge against the candidate's actual evidenced experience, not job-title
keyword overlap. A posting that merely repeats their buzzwords but sits at the
wrong seniority is a poor fit, not a strong one. Weigh seniority, domain,
scope of ownership, and location fit. Never invent experience the candidate
has not described.`

export async function scoreJob(profile, job) {
  const prompt = `## CANDIDATE\n${profileBlock(profile)}\n\n## JOB POSTING\n${postingBlock(job)}\n\nAssess this candidate against this posting.`

  const { data, model } = await generateJSON({
    system: SYSTEM,
    prompt,
    schema: SCORE_SCHEMA,
    effort: 'low',
  })

  const score = clampScore(data.score)
  const validTiers = ['exceptional', 'strong', 'possible', 'stretch', 'poor']
  let tier = String(data.tier || '').toLowerCase()
  if (!validTiers.includes(tier)) {
    // Gemini has no schema enforcement, so derive the tier from the score
    // rather than failing the row on a malformed label.
    tier =
      score >= 90 ? 'exceptional'
      : score >= 75 ? 'strong'
      : score >= 55 ? 'possible'
      : score >= 35 ? 'stretch'
      : 'poor'
  }

  return {
    score,
    tier,
    why_fit: String(data.why_fit || '').trim(),
    gaps: String(data.gaps || '').trim(),
    pitch_angle: String(data.pitch_angle || '').trim(),
    model,
  }
}

export { profileBlock, postingBlock }
