// LLM layer for match scoring and application drafting.
//
// Two providers, picked by which key is present:
//   ANTHROPIC_API_KEY → Claude (better nuanced fit reasoning)
//   GEMINI_API_KEY    → Gemini (zero new setup — same key the blog uses)
// Claude wins if both are set. Override with LLM_PROVIDER=gemini|claude.

import Anthropic from '@anthropic-ai/sdk'

const CLAUDE_MODEL = process.env.CLAUDE_MODEL || 'claude-opus-5'
// Same fallback chain as the blog pipeline (scripts/gemini.py), so a quota
// wall on one model doesn't fail the whole scan.
const GEMINI_MODELS = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash']

export function activeProvider(env = process.env) {
  const forced = (env.LLM_PROVIDER || '').toLowerCase()
  if (forced === 'claude') return env.ANTHROPIC_API_KEY ? 'claude' : null
  if (forced === 'gemini') return env.GEMINI_API_KEY ? 'gemini' : null
  if (env.ANTHROPIC_API_KEY) return 'claude'
  if (env.GEMINI_API_KEY) return 'gemini'
  return null
}

// ---------------------------------------------------------------------
// Claude
// ---------------------------------------------------------------------
let _anthropic = null
function anthropic() {
  if (!_anthropic) _anthropic = new Anthropic()
  return _anthropic
}

async function claudeJSON({ system, prompt, schema, effort = 'low' }) {
  const res = await anthropic().messages.create({
    model: CLAUDE_MODEL,
    max_tokens: 16000,
    system,
    output_config: {
      effort,
      format: { type: 'json_schema', schema },
    },
    messages: [{ role: 'user', content: prompt }],
  })
  if (res.stop_reason === 'refusal') throw new Error('Claude declined the request')
  const text = res.content.find(b => b.type === 'text')?.text
  if (!text) throw new Error('Claude returned no text block')
  return { data: JSON.parse(text), model: CLAUDE_MODEL }
}

async function claudeText({ system, prompt, effort = 'medium' }) {
  const res = await anthropic().messages.create({
    model: CLAUDE_MODEL,
    max_tokens: 16000,
    system,
    output_config: { effort },
    messages: [{ role: 'user', content: prompt }],
  })
  if (res.stop_reason === 'refusal') throw new Error('Claude declined the request')
  const text = res.content.filter(b => b.type === 'text').map(b => b.text).join('\n')
  return { text, model: CLAUDE_MODEL }
}

// ---------------------------------------------------------------------
// Gemini
// ---------------------------------------------------------------------
function stripFence(s) {
  return String(s).replace(/^\s*```(?:json)?\s*/i, '').replace(/```\s*$/, '').trim()
}

async function geminiCall(body) {
  const key = process.env.GEMINI_API_KEY
  let lastErr
  for (const model of GEMINI_MODELS) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        lastErr = new Error(`Gemini ${res.status} on ${model}`)
        // 429/5xx → try the next model in the chain.
        continue
      }
      const json = await res.json()
      const text = json?.candidates?.[0]?.content?.parts?.map(p => p.text).join('') || ''
      if (!text.trim()) {
        lastErr = new Error(`Gemini returned empty text on ${model}`)
        continue
      }
      return { text, model }
    } catch (err) {
      lastErr = err
    }
  }
  throw lastErr || new Error('All Gemini models failed')
}

async function geminiJSON({ system, prompt }) {
  const { text, model } = await geminiCall({
    systemInstruction: { parts: [{ text: system }] },
    contents: [{ role: 'user', parts: [{ text: prompt }] }],
    generationConfig: { responseMimeType: 'application/json', temperature: 0.2 },
  })
  return { data: JSON.parse(stripFence(text)), model }
}

async function geminiText({ system, prompt }) {
  const { text, model } = await geminiCall({
    systemInstruction: { parts: [{ text: system }] },
    contents: [{ role: 'user', parts: [{ text: prompt }] }],
    generationConfig: { temperature: 0.6 },
  })
  return { text, model }
}

// ---------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------
export async function generateJSON({ system, prompt, schema, effort }) {
  const provider = activeProvider()
  if (provider === 'claude') return claudeJSON({ system, prompt, schema, effort })
  if (provider === 'gemini') return geminiJSON({ system, prompt })
  throw new Error('No LLM key set (ANTHROPIC_API_KEY or GEMINI_API_KEY)')
}

export async function generateText({ system, prompt, effort }) {
  const provider = activeProvider()
  if (provider === 'claude') return claudeText({ system, prompt, effort })
  if (provider === 'gemini') return geminiText({ system, prompt })
  throw new Error('No LLM key set (ANTHROPIC_API_KEY or GEMINI_API_KEY)')
}
