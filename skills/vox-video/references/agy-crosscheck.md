# agy entity cross-check (supplementary)

`agy` (Gemini via the user's edu subscription) is a **supplementary** entity-layer cross-check layered
on the disciplined `mw + ffmpeg + vision` stack. It does TWO jobs only: (1) **correct garbled proper
nouns** in entity names — mw's weak spot (mw "store wrecks" / "Elisa's" / "Theo's habitashery" → agy
"store recs" / "Illisa's" / "Theo's Haberdashery"); (2) **surface on-screen entities** the 5-frame
%-sample missed (agy reads the WHOLE video). It is NOT a source of spoken quotes, timestamps/frame
anchors, sentiment, or comments — the stack stays **source-of-record** for all of those. agy is
supplementary, never a replacement.

## Soft gating (NOT a hard prereq)
Unlike `mw` / `ffmpeg` / `tiktok-cli` (hard prereqs that HALT when missing), `agy` is SOFT-probed at
bootstrap with `agy --help`:
- present → cross-check **ENABLED**.
- absent → cross-check **DISABLED**, recorded as a coverage note ("agy entity cross-check unavailable —
  names are mw/vision-only"); the pipeline PROCEEDS normally. This is **never a halt** — the contrast
  with the hard prereqs.

## The call (Phase-1 ingest, video-only, before media cleanup)
Run ONCE per downloaded video mp4, **before `video.mp4` is removed** (agy needs the file present). Photo
carousels SKIP agy (record `agy: skipped`) — they keep their vision-on-slides path.

Model `Gemini 3.1 Pro (Low)` (passed explicitly; agy's own default is Gemini 3.5 Flash Medium). Fixed
deterministic prompt → three parseable sections:

    agy -p "Analyze the video file <id>.mp4 in this workspace. Produce EXACTLY three sections:
    ## spoken — verbatim speech only; if there is no speech write exactly: (no speech)
    ## on-screen — any text visible on screen; if none write: (none)
    ## entities — bullet list of every business/place/brand name, each tagged (spoken) or (on-screen); if none write: (none)
    Do not invent or infer anything not present in the file." \
      --model "Gemini 3.1 Pro (Low)" --add-dir <workdir> --dangerously-skip-permissions

Write the result to `<workdir>/<id>/agy.md`.

## The three mandatory guards (each earned from live validation)
1. **Hard external timeout (~150s per call).** agy can HANG past its own `--print-timeout` on malformed
   media (a 70s-video / 15s-audio desync hung ~42 min). Bound every call and kill on overrun. (Real
   videos returned well under 150s.)
2. **Success judged by OUTPUT, not exit code.** agy returned exit 0 with `Error: timed out waiting for
   response` as its body. A run is a FAILURE if its output is empty, is missing the `##` section
   markers, or contains `Error: timed out`.
3. **Retry once on flake.** ~1/3 of clean-input runs flaked (timeout error). On a failed output-check,
   retry exactly once, then give up.

On give-up: write `agy: unavailable (<reason>)` and CONTINUE — never abort the video or the collection.

## agy.md artifact shape
    # agy cross-check — <id>
    status: ok            # or: unavailable (<reason>) | skipped (photo) | disabled (agy absent)
    ## spoken
    <verbatim, or (no speech)>
    ## on-screen
    <text, or (none)>
    ## entities
    - <name> (spoken|on-screen)

`status.json` gains an `agy` field: `ok | unavailable | skipped | disabled`. Re-runs skip resolved items.

## Reconciliation rules (Phase-2 extraction; consume agy.md at the ENTITY layer only)
These layer onto the five honesty rules in [digest-extension](digest-extension.md) and NEVER override them.

- **R-A1 — Spelling reconciliation, by precedence.** On a same-referent spelling disagreement (matched by
  token similarity), the canonical name follows: (1) an on-screen **NAME CARD** read by vision (storefront
  sign / Maps card — the business's own text, authoritative); (2) `agy`; (3) the `mw` transcript (weakest,
  mishears names). So agy overrides mw for SPOKEN-only entities but does NOT override a vision-read
  on-screen name card. The claim's quote text + timestamp/frame provenance stay exactly as the stack
  recorded them; log the correction transparently ("canonical name per agy cross-check; mw heard 'Elisa's'").
- **R-A2 — agy-only on-screen entities.** An on-screen entity agy caught but the frame-sample missed is
  ADDED as a claim sourced `agy on-screen (no frame anchor)`, at **lower confidence** than a frame-anchored
  on-screen claim; it must still corroborate downstream — never promoted on agy alone.
- **R-A3 — No phantom quotes via agy.** agy NEVER creates a spoken-claim quote. Honesty Rule 2 still
  binds: a spoken quote exists ONLY if the **stack's** transcript status is `ok`. agy touches entity
  **spelling** only; we never quote from agy's transcript.
- **R-A4 — agy never deletes.** agy misses don't remove stack claims; stack entities agy missed are kept.
  Disagreements resolve as R-A1 or R-A2, never a deletion.
- **R-A5 — Per-video unavailability is recorded.** `agy: unavailable` → extract stack-only for that video
  and note in the digest's "sources that failed" that the cross-check didn't run (a possibly-garbled name
  isn't silently trusted as verified).
