# vox-video `agy` entity cross-check (design)

**Status:** approved 2026-06-07. A single-repo (vox) refinement of the shipped `vox-video` tier that
adds `agy` (Gemini via the user's edu subscription) as a SUPPLEMENTARY entity-layer cross-check on top
of the `mw + ffmpeg + vision` ingest stack. Subscription-native (no paid API, no card).

## 1. Purpose
The shipped `vox-video` tier extracts cited place claims from TikTok videos via a disciplined stack:
`tiktok-cli` download → `mw` (parakeet-v3) transcript → `ffmpeg` %-sampled frames → Claude vision
on-screen text → comments. That stack has two documented weaknesses that hit vox-video's core job
(resolving *place names* for downstream Maps/web corroboration):

1. **Garbled proper nouns in the transcript.** `mw` mishears business/place names — a wrong entity
   name silently fails its Maps/web lookup, so the place is dropped or mis-ranked.
2. **On-screen coverage gaps from %-sampling.** The 5-frame sample (12/30/50/70/88%) misses on-screen
   cards (addresses, Maps overlays) that appear at other timestamps.

`agy` processes the whole mp4 in one call (visuals + on-screen text + audio) and — validated below — is
materially **more accurate on proper nouns** and **more complete on on-screen text** than the stack.
This design slots `agy` in as a per-video cross-check that **corrects entity spellings** and **surfaces
missed on-screen entities**, while the disciplined stack stays **source-of-record** for quotes,
timestamps, and confidence. `agy` is supplementary, never a replacement.

## 2. Pre-design validation (2026-06-07) — the findings this design is built on
Run against the cached rigor workdir + fresh `agy` calls. These findings are load-bearing:

- **Consistency (deep, full-output) on the `@ladybaileybee` proper-noun stress video:** `agy` corrected
  every proper-noun error `mw` made — `mw` "store **wrecks**"/"**Elisa's**"/"Theo's **habitashery**"/
  "**Distress** Fest" → `agy` correct "store recs"/"Illisa's"/"Theo's Haberdashery"/"Distressed Fest" —
  and read **all 9** on-screen Apple-Maps store cards (with neighborhoods) vs the stack's 2 sampled
  frames. When prompted for explicit sections, `agy` **kept spoken vs on-screen separated**; what it
  lacks is **per-claim timestamps** (`@0:47` / `frame f3_50pct`). So the stack stays provenance-of-record
  for *where-in-video*; `agy` is the accuracy + coverage cross-check for *entity spelling/completeness*.
- **`agy` is intermittently flaky (the central robustness finding):** a silence test on a clean
  black+silent fixture was **2/3 clean** `(no speech)` but **1/3 returned `Error: timed out waiting for
  response`** — and **exit code was 0 even on that timeout error**. Success MUST be judged by OUTPUT
  inspection, not `$?`.
- **`agy` can HANG indefinitely (~42 min, past its own `--print-timeout`)** on malformed media (a fixture
  with 70s video vs 15s audio desync). Each call MUST be wrapped in a HARD EXTERNAL timeout.
- **Broader n=3–5 consistency was blocked** by TikTok anti-bot (re-downloading the other rigor mp4s
  failed `InvalidResponseException: 200` on every retry). The deep n=1 + the prior session's n=1 are
  decisive on the qualitative direction; more breadth is optional if revisited.

## 3. Goals / non-goals
**Goals**
- Add a per-video `agy` cross-check to Phase-1 ingest, producing a parseable `agy.md` artifact, with the
  three mandatory robustness guards (hard external timeout, output-based success check, retry-once).
- Reconcile entities at Phase-2 extraction: prefer `agy`'s spelling for the canonical entity name; add
  `agy`-only on-screen entities at lower confidence — without ever violating the existing five honesty
  rules (above all, no phantom spoken quotes).
- Make `agy` strictly supplementary and SOFT-gated: absent/flaky/unavailable `agy` degrades silently and
  is recorded; it NEVER halts or blocks the pipeline.
- Keep the vox repo gate green (pytest / ruff / `validate_skills.py`).

**Non-goals**
- **Replacing any stack signal.** `agy` never becomes the source of a spoken quote, a timestamp, a
  sentiment read, or comments. (Rejected: full independent second-extraction — too close to replacement,
  leaks `agy`'s provenance-blur into claims.)
- **agy on photo carousels.** v1 `agy` cross-check is VIDEO-only (mirrors the transcript branch); photo
  carousels keep their existing vision-on-slides path and record `agy: skipped`.
- **Targeted/triggered invocation** (agy only on corroboration failure) — rejected: cross-phase
  coupling, undetectable trigger from `mw` output, hard to test. Per-video default-on is simpler.
- Any orchestrator (`vox/SKILL.md`) routing change, or any change to the hard `mw`/`ffmpeg`/`tiktok-cli`
  prerequisites, the existing five honesty rules, or the digest contract's 7 sections.

## 4. Component 1 — Bootstrap: soft `agy` probe
The current bootstrap HARD-HALTS if `mw`/`ffmpeg`/`tiktok-cli` are missing. `agy` is added as a SOFT
probe (`agy --help`), with a fundamentally different failure mode:
- **`agy` present** → entity cross-check **enabled**.
- **`agy` absent** → cross-check **disabled**, recorded as a coverage note ("agy entity cross-check
  unavailable — names are mw/vision-only"), and the pipeline **proceeds normally**. NOT a halt.

This soft/hard split is the explicit contrast: the videos themselves (mw/ffmpeg/tiktok-cli) are the
source and remain mandatory; `agy` is an optional accuracy layer.

## 5. Component 2 — Phase-1 ingest: the `agy` step → `agy.md`
A new pluggable, cached ingest stage, **video-only**, run **on the downloaded mp4 BEFORE media cleanup**
(the pipeline removes `video.mp4` after extract unless `--keep-media`; `agy` needs the mp4 present).

**Invocation:** fixed deterministic prompt, model `Gemini 3.1 Pro (Low)` (the validated accuracy/cost
point; note `agy`'s own default is Gemini 3.5 Flash Medium, so the model is passed explicitly),
`--add-dir <workdir>` `--dangerously-skip-permissions` `-p "<prompt>"`. The prompt asks for EXACTLY
three sections so the output is parseable: `## spoken` (verbatim or `(no speech)`), `## on-screen` (text
or `(none)`), `## entities` (bullet list, each tagged `(spoken)` or `(on-screen)`), with an explicit
"do not invent anything" instruction.

**The three mandatory robustness guards (each earned from §2):**
1. **Hard external timeout (~150s per call).** `agy` can hang past its own `--print-timeout`; the agent
   bounds each call and kills on overrun. (Real videos returned well under 150s in validation; the hang
   was the lone malformed-media outlier.)
2. **Success judged by OUTPUT, not exit code.** `agy` returned exit 0 with `Error: timed out` as its
   body. A run is a FAILURE if its output is empty, is missing the expected `##` section markers, or
   contains `Error: timed out`.
3. **Retry once on flake.** On a failed output-check, retry exactly once (covers the ~1/3 flake rate),
   then give up.

**On give-up:** write `agy: unavailable (<reason>)` for that video and continue — never abort the video
or the collection. `status.json` gains an `agy` field: `ok | unavailable | skipped | disabled`. Re-runs
skip already-resolved items, exactly like every other cached stage.

**`agy.md` artifact shape (deterministic, parseable):**
```
# agy cross-check — <id>
status: ok                 # or: unavailable (<reason>) | skipped (photo) | disabled (agy absent)
## spoken
<verbatim text, or (no speech)>
## on-screen
<text, or (none)>
## entities
- <name> (spoken|on-screen)
```

## 6. Component 3 — Phase-2 extraction: reconciliation rules
`agy.md` is consumed ONLY at the entity layer. These rules layer onto the existing five honesty rules
and never override them.

- **R-A1 — Spelling reconciliation, by precedence.** When sources disagree on an entity's spelling
  (matched as the same referent by token similarity), the canonical name follows this precedence:
  **(1) an on-screen NAME CARD** read by the vision pass — a storefront sign / Maps card / business
  overlay is the business's own text and is authoritative; **(2) `agy`** (validated more accurate than
  `mw` on proper nouns); **(3) the `mw` transcript** (weakest — mishears names). So `agy` overrides
  `mw` for SPOKEN-only entities, but does NOT override a vision-read on-screen name card. In every case
  the claim's **quote text and timestamp/frame provenance stay exactly as the stack recorded them**, and
  the correction is logged transparently (e.g. "canonical name per agy cross-check; mw heard 'Elisa's'").
  `agy` fixes the name used for corroboration, not the quote.
- **R-A2 — agy-only on-screen entities.** When `agy` lists an on-screen entity the frame-sample missed,
  ADD it as a claim sourced `agy on-screen (no frame anchor)`, at **lower confidence** than a
  frame-anchored on-screen claim (no exact frame). It must still corroborate downstream like any
  candidate — never promoted on `agy` alone.
- **R-A3 — No phantom quotes via agy (critical guardrail).** `agy` NEVER creates a spoken-claim quote.
  Honesty Rule 2 still binds: a spoken quote exists only if the **stack's** transcript status is `ok`.
  Even though `agy` produces a transcript, we never quote from it — it touches entity *spelling* only.
  This contains `agy`'s provenance-blur and keeps it supplementary.
- **R-A4 — agy never deletes.** `agy` misses don't remove stack claims; stack entities `agy` didn't
  catch are kept. Disagreements resolve as R-A1 (spelling) or R-A2 (agy-only add), never a deletion.
- **R-A5 — Per-video unavailability is recorded.** If `agy: unavailable` for a video, extraction
  proceeds stack-only and the digest notes the cross-check didn't run for it — so a possibly-garbled
  name isn't silently trusted as verified.

## 7. Component 4 — Digest / output
- **Sources that failed / blocked** records per-video `agy` unavailability and global `agy`-disabled.
- Corrected names carry the transparent "via agy cross-check" note (audit trail).
- `agy`-only entities carry their lower-confidence + "no frame anchor" label.
- All other digest sections and the 7-section contract are unchanged.

## 8. Error handling (consolidated)
No path halts or blocks the pipeline:
- `agy` absent at bootstrap → disabled globally, noted.
- `agy` hang → external timeout kills it → retry once → `unavailable`.
- `agy` flake (empty / missing markers / `Error: timed out`, even at exit 0) → output-check catches →
  retry once → `unavailable`.
- `agy` on malformed/desync media → same timeout/retry/`unavailable` path.

## 9. Testing
vox repo gate: `pytest` / `ruff check tools tests eval` / `validate_skills.py skills`. `vox-video` is
pure prose (no Python), so:
- **New contract test** (`tests/test_video_agy.py`, sibling to `test_routing.py`) keyed on stable concept
  words: assert the skill files DOCUMENT (a) `agy` is an entity-layer cross-check and the `mw`/vision
  stack stays source-of-record; (b) no-phantom-quotes still binds (R-A3); (c) `agy`-unavailable is
  non-halting; (d) the three guards are present (hard timeout, output-not-exit-code, retry-once). Locks
  the guidance against silent drift.
- `validate_skills.py` stays `[ok]` for every skill.
- **Eval golden** (`eval/goldens/video-collection.md`) gains expectation lines: proper-noun correction
  shown transparently; `agy` never the source of a spoken quote; `agy`-unavailable noted, not halted.

## 10. Files created / changed (single repo: vox)
- `skills/vox-video/SKILL.md` — bootstrap soft-probe; Phase-1 `agy` step; Phase-2 reconciliation pointer.
- `skills/vox-video/references/ingest-playbook.md` — the `agy` ingest stage + guards + `status.json`
  field + workdir `agy.md`.
- `skills/vox-video/references/digest-extension.md` — R-A1..R-A5 + the digest/output notes.
- `skills/vox-video/references/agy-crosscheck.md` (NEW) — exact prompt, model, guards, artifact shape,
  reconciliation rules in one focused reference.
- `tests/test_video_agy.py` (NEW) — the contract test above.
- `eval/goldens/video-collection.md` — the `agy` expectation lines.

## 11. Risks
- **`agy` spelling is also wrong on a name** → R-A1 adopts a wrong canonical name. Mitigated: the entity
  must still corroborate on Maps/web; a name neither source can find is disclosed, not faked. `agy` is a
  cross-check, not an oracle.
- **`agy` flake rate higher in practice than 1/3** → more videos fall to stack-only; recorded per R-A5,
  never silently. The pipeline's value is unchanged (stack is source-of-record); only the accuracy layer
  thins, transparently.
- **Cost** (one `agy` call per entity-bearing video, edu subscription) → acceptable: not metered API,
  incremental vs the existing heavy per-video pipeline, and capped by the hard timeout + single retry.
