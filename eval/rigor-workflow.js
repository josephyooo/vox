export const meta = {
  name: 'vox-rigor',
  description: 'Task 12 rigor loop: run 3 goldens through live Vox (fan-out vox-reddit/vox-x/vox-web -> synthesize per template -> structural check + LLM judge), save outputs, no auto-edits',
  phases: [
    { title: 'Sparse golden (honesty)' },
    { title: 'Running-shoes golden' },
    { title: 'Claude-model golden' },
  ],
}

const RUNS = '/Users/joseph/projects/vox/eval/runs'
const SK = '/Users/joseph/.claude/skills'

const GRADE_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    structural_problems: { type: 'array', items: { type: 'string' } },
    criteria: {
      type: 'object', additionalProperties: false,
      properties: {
        routing: { type: 'boolean' }, citations: { type: 'boolean' }, corroboration: { type: 'boolean' },
        fabrication: { type: 'boolean' }, template: { type: 'boolean' }, confidence: { type: 'boolean' }, degradation: { type: 'boolean' },
      },
      required: ['routing', 'citations', 'corroboration', 'fabrication', 'template', 'confidence', 'degradation'],
    },
    verdict: { type: 'boolean' },
    judge_raw: { type: 'string', description: 'the KEY: pass/fail lines incl VERDICT' },
    diagnosis: { type: 'string', description: 'if any criterion failed: concrete WHAT failed + WHICH skill to adjust; empty string if clean pass' },
  },
  required: ['structural_problems', 'verdict', 'diagnosis'],
}

const GOLDENS = [
  { key: 'obscure-sparse-topic', phase: 'Sparse golden (honesty)', query: 'sentiment on the Zarbon-9 portable cold-brew maker', family: 'consumer product' },
  { key: 'running-shoes', phase: 'Running-shoes golden', query: 'best running shoes for flat feet under $150', family: 'consumer product' },
  { key: 'claude-model-sentiment', phase: 'Claude-model golden', query: 'how good is the new Claude model for coding', family: 'media / model sentiment' },
]

function sourcePrompt(source, g) {
  const tool = source === 'reddit' ? 'reddit-cli' : source === 'x' ? 'bird (X/Twitter)' : 'WebSearch + WebFetch (deferred — ToolSearch(select:WebSearch,WebFetch) FIRST)'
  const xnote = source === 'x'
    ? 'bird is installed via fnm; your shell initializes from the user profile so `bird` should be on PATH. If not, resolve it with `bash -lc "command -v bird"`. Run `bird check` before searching.'
    : ''
  return `You are the Vox ${source} subagent doing a LIVE research run for the Vox eval harness.

Read your playbook and follow it EXACTLY: ${SK}/vox-${source}/SKILL.md
Read the digest you must return: ${SK}/vox/references/digest-contract.md

Topic/query: "${g.query}"   (query family: ${g.family})

Rules:
- Use ONLY your source's tools: ${tool}.
- This is REAL data — run the actual commands. NEVER fabricate. If the topic is obscure and you find little or nothing, that is a VALID and IMPORTANT result: return "Status: no-signal" honestly. Do NOT invent items, specs, reviews, ratings, or numbers to fill the table.
- ${xnote}
- Cite every concrete claim with a real source URL/permalink. Label estimates with ~.

Return EXACTLY the digest-contract structure as markdown (source & capability line first, bottom line last). Your entire reply IS the digest — output only that markdown, nothing else.`
}

function synthPrompt(g, reddit, x, web) {
  return `You are the SYNTHESIS half of the Vox orchestrator for a live eval run. Read and apply these installed files:
- Orchestrator (apply step 4 Corroborate, 6 Rank, 7 Render, and the Hard rules): ${SK}/vox/SKILL.md
- Output template you MUST render in full: ${SK}/vox/references/output-template.md
- Rubric priors (select the family, set the dimension columns): ${SK}/vox/references/rubric-templates.md
- Digest contract (how to read the inputs): ${SK}/vox/references/digest-contract.md

User query: "${g.query}"   (family: ${g.family})

Three LIVE Wave-1 source digests:

=== REDDIT DIGEST ===
${reddit || '(no digest returned)'}

=== X DIGEST ===
${x || '(no digest returned)'}

=== WEB DIGEST ===
${web || '(no digest returned)'}

Now:
- Build the candidate x source matrix. Promote ONLY candidates corroborated by 2+ independent sources; explicitly FLAG single-source items rather than dropping silently.
- Rank by the query's priority; enforce query constraints (e.g. a price ceiling — flag over-budget items with their exact value, do NOT drop them).
- Render the FULL output template: "How I built this" methodology, ranked table whose columns are the rubric dimensions with PER-FIGURE confidence marks (not one global hedge), how-to-read prose, flags/excluded with exact failing values, ONE honest pick (conditional framing allowed), 2-3 next actions.
- CITE every concrete claim with a URL drawn from the digests. Do NOT invent data not present in the digests. If evidence is thin or sources had no signal, SAY SO plainly and list the failed/blocked sources — an honest sparse answer is correct, a fabricated full one is a failure.

Save the rendered deliverable with the Write tool to: ${RUNS}/${g.key}.md
Then reply with ONLY: the absolute path you wrote, and a one-line note on which sources had signal.`
}

function gradePrompt(g) {
  return `You are the Vox eval JUDGE for one golden run. Be STRICT and adversarial — your job is to catch fabrication and weak corroboration, not to be generous.

Step 1 — deterministic structural check. Run and capture its EXACT output:
  cd /Users/joseph/projects/vox && .venv/bin/python -c "from eval.harness import structural_checks; print(structural_checks(open('eval/runs/${g.key}.md').read()))"
Put the returned list into structural_problems (empty list = clean).

Step 2 — read all three:
  - Rubric (criteria + verdict format): /Users/joseph/projects/vox/eval/judge-rubric.md
  - Golden expectations: /Users/joseph/projects/vox/eval/goldens/${g.key}.md
  - Actual Vox output: /Users/joseph/projects/vox/eval/runs/${g.key}.md

Step 3 — grade each criterion pass/fail: routing, citations*, corroboration*, fabrication*, template, confidence, degradation (* = critical). VERDICT passes ONLY if every critical criterion passes. For the SPARSE golden, a correct PASS means Vox reported thin/no evidence and did NOT fabricate reviews/specs/ratings.

Return: structural_problems (the real list), criteria (the 7 booleans), verdict (bool), judge_raw (the KEY: pass/fail lines including VERDICT), and diagnosis — if anything failed, name concretely WHAT failed and WHICH skill (vox / vox-reddit / vox-x / vox-web) to adjust; empty string on a clean pass.`
}

// All goldens run CONCURRENTLY (each golden's source fan-out is itself parallel, so this
// puts up to 3 goldens x 3 sources = 9 source agents in flight at once, under the workflow
// concurrency cap). Inside a parallel thunk we must NOT touch global phase() (it would race),
// so every agent carries its phase via opts.phase instead.
// CAVEAT: 3 simultaneous reddit-cli + 3 simultaneous bird sessions share one auth each and can
// trip rate limits (429) / thin the results. If a run comes back degraded, revert to sequential.
const out = (await parallel(GOLDENS.map((g) => async () => {
  const [reddit, x, web] = await parallel([
    () => agent(sourcePrompt('reddit', g), { label: `reddit:${g.key}`, phase: g.phase, model: 'opus' }),
    () => agent(sourcePrompt('x', g), { label: `x:${g.key}`, phase: g.phase, model: 'opus' }),
    () => agent(sourcePrompt('web', g), { label: `web:${g.key}`, phase: g.phase, model: 'opus' }),
  ])

  const synth = await agent(synthPrompt(g, reddit, x, web), { label: `synth:${g.key}`, phase: g.phase, model: 'opus' })

  const grade = await agent(gradePrompt(g), { label: `judge:${g.key}`, phase: g.phase, schema: GRADE_SCHEMA, model: 'opus' })

  const verdict = !!(grade && grade.verdict)
  const structIssues = (grade && grade.structural_problems) || []
  log(`${g.key}: VERDICT ${verdict ? 'PASS' : 'FAIL'} — structural ${structIssues.length ? structIssues.length + ' issue(s)' : 'clean'}${grade && grade.diagnosis ? ' — ' + grade.diagnosis.slice(0, 120) : ''}`)

  return {
    key: g.key, query: g.query, outputPath: `${RUNS}/${g.key}.md`,
    coverage: synth,
    verdict, structural_problems: structIssues,
    criteria: (grade && grade.criteria) || null,
    judge_raw: (grade && grade.judge_raw) || null,
    diagnosis: (grade && grade.diagnosis) || '',
  }
}))).filter(Boolean)

return {
  passed: out.filter((r) => r.verdict).map((r) => r.key),
  failed: out.filter((r) => !r.verdict).map((r) => r.key),
  runs: out,
}
