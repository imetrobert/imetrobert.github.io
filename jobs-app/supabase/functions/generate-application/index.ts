// Supabase Edge Function: generate-application
//
// Drafts a tailored cover letter and CV for one posting, grounded in the
// profile stored in job_profile. Saves both to job_applications and returns
// them to the browser.
//
// This runs as an edge function rather than in the scan workflow because it's
// interactive — you click, you wait a few seconds, you read the draft. The
// monthly scan stays in GitHub Actions where it has minutes to work with.
//
// Deploy: Supabase Dashboard → Edge Functions → Deploy a new function →
// name it exactly "generate-application", paste this file, deploy (keep
// "Verify JWT" ON — that's what restricts it to your logged-in session).
// Or via CLI: supabase functions deploy generate-application
//
// Secrets (Dashboard → Edge Functions → Secrets):
//   GEMINI_API_KEY  (required)
//   ANTHROPIC_API_KEY (optional upgrade — Claude is used only if this is set;
//   nothing here needs a paid Claude account)

import { createClient } from 'npm:@supabase/supabase-js@2'

const cors = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, 'Content-Type': 'application/json' },
  })
}

const CLAUDE_MODEL = Deno.env.get('CLAUDE_MODEL') || 'claude-opus-5'
const GEMINI_MODELS = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash']

async function callClaude(system: string, prompt: string): Promise<string> {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': Deno.env.get('ANTHROPIC_API_KEY')!,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: CLAUDE_MODEL,
      max_tokens: 16000,
      system,
      output_config: { effort: 'medium' },
      messages: [{ role: 'user', content: prompt }],
    }),
  })
  if (!res.ok) throw new Error(`Claude ${res.status}: ${(await res.text()).slice(0, 300)}`)
  const data = await res.json()
  if (data.stop_reason === 'refusal') throw new Error('Claude declined the request')
  return (data.content || [])
    .filter((b: { type: string }) => b.type === 'text')
    .map((b: { text: string }) => b.text)
    .join('\n')
}

async function callGemini(system: string, prompt: string): Promise<string> {
  const key = Deno.env.get('GEMINI_API_KEY')!
  let lastErr: Error | null = null
  for (const model of GEMINI_MODELS) {
    try {
      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            systemInstruction: { parts: [{ text: system }] },
            contents: [{ role: 'user', parts: [{ text: prompt }] }],
            generationConfig: { temperature: 0.6 },
          }),
        }
      )
      if (!res.ok) {
        lastErr = new Error(`Gemini ${res.status} on ${model}`)
        continue
      }
      const data = await res.json()
      const text = (data?.candidates?.[0]?.content?.parts || [])
        .map((p: { text: string }) => p.text)
        .join('')
      if (text.trim()) return text
      lastErr = new Error(`Gemini returned empty text on ${model}`)
    } catch (err) {
      lastErr = err as Error
    }
  }
  throw lastErr || new Error('All Gemini models failed')
}

async function generate(system: string, prompt: string): Promise<string> {
  if (Deno.env.get('ANTHROPIC_API_KEY')) return callClaude(system, prompt)
  if (Deno.env.get('GEMINI_API_KEY')) return callGemini(system, prompt)
  throw new Error('No LLM key configured — set GEMINI_API_KEY in Edge Functions → Secrets')
}

const SYSTEM = `You write job application documents for one specific candidate applying to one specific role.

Hard rules:
- Use ONLY facts present in the candidate's profile and resume. Never invent an employer, title, date, metric, certification, or degree. If the posting asks for something the candidate does not have, do not manufacture it — either omit it or address it honestly as transferable experience.
- Write in the candidate's own register: direct, specific, and confident without inflation. No "I am writing to express my keen interest", no "passionate about leveraging synergies", no filler superlatives.
- Lead with the single strongest reason this candidate fits this role. Earn the rest of the letter with concrete evidence — scope owned, outcomes, numbers already in the resume.
- Reference the actual company and role. If the posting names a specific problem, challenge, or product, speak to it directly.
- Cover letter: under 300 words, four short paragraphs at most, no bullet lists.

POSITIONING A LONG CAREER

This candidate is late-career with deep experience. That is an asset, and the documents must read that way — but resume screening frequently filters experienced candidates before a human ever reads the application. Write to survive that screen without ever misrepresenting anything:

- Lead with current, in-demand capability, not with longevity. Never open with "25+ years of experience" or similar — it invites a filter before it demonstrates anything. Open with recent, specific, quantified impact.
- Foreground the most recent and most current work, especially anything in a presently in-demand area. The strongest available counter to any assumption that a long career means dated skills is concrete evidence of current work. Put it first and be specific about it.
- On the CV, give full detail to roughly the last 12–15 years. Compress everything earlier into a single short "Earlier career" line naming the employers and the nature of the work, without a year-by-year breakdown. This is standard executive-CV practice and loses nothing that matters to a hiring manager.
- Never include education graduation years, or any date that exists only to establish chronology rather than to demonstrate achievement.
- Emphasise appetite for the actual work of the role, not just oversight of it. The most common reason an experienced candidate is passed over is a fear that they want a title rather than the job.
- Never apologise for the depth of the candidate's experience, never call attention to career length as something to be explained, and never write a line that draws attention to age. Simply lead with what is most relevant and current.
- If a screening risk is supplied below, write to defuse it — through emphasis and framing, never by hiding or misstating a fact.

Output format — return exactly these two sections and nothing else:

===COVER_LETTER===
<the letter, ready to send, no placeholders>

===CV===
<the full CV in Markdown, reordered and reworded to foreground what this role wants. Same facts as the source resume — same employers and titles — but with emphasis, phrasing and ordering tuned to the posting, and recent work given the most space.>`

Deno.serve(async req => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: cors })

  try {
    const authHeader = req.headers.get('Authorization')
    if (!authHeader) return json({ error: 'Not authenticated' }, 401)

    // Verify the caller is a real logged-in user before spending an LLM call.
    const userClient = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_ANON_KEY')!,
      { global: { headers: { Authorization: authHeader } } }
    )
    const { data: { user } } = await userClient.auth.getUser()
    if (!user) return json({ error: 'Not authenticated' }, 401)

    const { posting_id } = await req.json()
    if (!posting_id) return json({ error: 'posting_id is required' }, 400)

    const db = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    )

    const [{ data: profile }, { data: job }, { data: match }] = await Promise.all([
      db.from('job_profile').select('*').eq('id', 1).single(),
      db.from('job_postings').select('*').eq('id', posting_id).single(),
      db.from('job_matches').select('*').eq('posting_id', posting_id).maybeSingle(),
    ])

    if (!job) return json({ error: 'Posting not found' }, 404)
    if (!profile?.resume_text) {
      return json({ error: 'Add your resume in the Profile tab first — there is nothing to tailor.' }, 400)
    }

    // Regenerating documents must not rewind the pipeline: if you've already
    // marked this applied/interviewing/offer, that status survives.
    const { data: existingApp } = await db
      .from('job_applications')
      .select('status')
      .eq('posting_id', posting_id)
      .maybeSingle()
    const keepStatus =
      existingApp?.status && !['interested', 'generating', 'ready'].includes(existingApp.status)
        ? existingApp.status
        : null

    await db
      .from('job_applications')
      .upsert(
        { posting_id, status: keepStatus || 'generating', updated_at: new Date().toISOString() },
        { onConflict: 'posting_id' }
      )

    const prompt = [
      '## CANDIDATE',
      profile.headline ? `Headline: ${profile.headline}` : '',
      profile.location ? `Based in: ${profile.location}` : '',
      profile.summary ? `Summary: ${profile.summary}` : '',
      '',
      '### RESUME',
      profile.resume_text,
      '',
      '## THE ROLE',
      `Title: ${job.title}`,
      job.company ? `Company: ${job.company}` : '',
      job.location ? `Location: ${job.location}` : '',
      '',
      (job.description || '').slice(0, 8000),
      '',
      match?.pitch_angle ? `## SUGGESTED ANGLE\n${match.pitch_angle}` : '',
      match?.gaps ? `## KNOWN GAPS TO HANDLE HONESTLY\n${match.gaps}` : '',
      match?.overqualification_risk
        ? `## SCREENING RISK TO WRITE AGAINST\n${match.overqualification_risk}`
        : '',
      '',
      'Write the cover letter and the tailored CV.',
    ]
      .filter(Boolean)
      .join('\n')

    const raw = await generate(SYSTEM, prompt)

    // Tolerate the model varying the marker spacing or dropping the CV block.
    const letterMatch = raw.match(/===\s*COVER_LETTER\s*===\s*([\s\S]*?)(?:===\s*CV\s*===|$)/i)
    const cvMatch = raw.match(/===\s*CV\s*===\s*([\s\S]*)$/i)
    const cover_letter = (letterMatch?.[1] || raw).trim()
    const tailored_cv = (cvMatch?.[1] || '').trim() || null

    await db.from('job_applications').upsert(
      {
        posting_id,
        status: keepStatus || 'ready',
        cover_letter,
        tailored_cv,
        generated_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      { onConflict: 'posting_id' }
    )

    return json({ cover_letter, tailored_cv })
  } catch (err) {
    return json({ error: (err as Error).message }, 500)
  }
})
