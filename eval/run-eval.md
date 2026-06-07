# Running the Vox eval loop

1. Pick a golden in `eval/goldens/`. Run its `## Query` through Vox (invoke `/vox <query>` in a
   Claude Code session with the skills installed).
2. Capture Vox's full output to a file, e.g. `/tmp/vox-out.md`.
3. Deterministic layer:
   `.venv/bin/python -c "from eval.harness import structural_checks; import sys; print(structural_checks(open('/tmp/vox-out.md').read()))"`
   — must print `[]`.
4. Semantic layer: dispatch a judge subagent with `eval/judge-rubric.md` + the query + the output.
   Feed its verdict text to `parse_judge_verdict`; `VERDICT` must be `pass`.
5. If anything fails, fix the orchestrator/source skills, reinstall (`./install.sh`), and repeat.
   Loop until all goldens pass clean. THIS is "loop until rigorous".

## Automated path (workflow)

`eval/rigor-workflow.js` runs the whole loop as a multi-agent workflow. Per golden it fans out the
three source subagents (`vox-reddit`/`vox-x`/`vox-web`) on live data, synthesizes the deliverable per
the output template, saves it to `eval/runs/<golden>.md`, then runs the structural check + the LLM
judge and returns each verdict. All three goldens run concurrently. It does NOT auto-edit skills —
review any failure + the judge's diagnosis, fix the relevant skill, `./install.sh`, re-run.

Run it from a Claude Code session (uses the Workflow tool → your subscription, no API):

    Workflow({ scriptPath: "<repo>/eval/rigor-workflow.js" })

Prerequisites: skills installed (`./install.sh`); `reddit-cli` and `bird` on PATH and authenticated
(`bird check`). Outputs land in `eval/runs/` (gitignored).

Caveat: concurrent goldens put 3 simultaneous `reddit-cli` + 3 simultaneous `bird` sessions on one
auth each, which can trip rate limits (429) and thin results. If a run comes back degraded, switch
the `parallel(GOLDENS.map(...))` back to a sequential `for` loop in the script.

## Browser-tier rigor (manual, capability-gated)

The browser tier needs a paired Chrome, which the headless rigor workflow can't do — so grade it
manually:
1. Install + pair: `./install.sh`, open Chrome, confirm the `claude-in-chrome` MCP can connect.
2. In an interactive Claude session run `/vox best ramen near Union Square under $20 within a short
   transit detour` (the `eval/goldens/browser-places.md` query). Capture to
   `eval/runs/browser-places.md`.
3. Grade with the SAME layers: `structural_checks` must print `[]`; dispatch the judge with
   `eval/judge-rubric.md` + the query + the output; `VERDICT` must be `pass`.
4. Sanity-check the HALT path: with Chrome NOT connected, the same query must STOP and report (not
   fabricate); re-running with `--web-fallback` must degrade with explicit lower-confidence marks.

## Video-tier rigor (manual, capability-gated)
The video tier needs local `mw` + `ffmpeg` + `tiktok-cli` + a real ms_token, which the headless rigor
workflow lacks — so run it by hand, the analogue of the browser-tier rigor:
1. Ensure prereqs: `mw --help`, `ffmpeg -version`, `tiktok-cli doctor` all green.
2. Run `eval/goldens/video-collection.md`'s query through `/vox` with a real PUBLIC collection URL,
   Chrome paired for the Maps corroboration.
3. Capture to `eval/runs/video-collection.md`; grade with both layers — `structural_checks` must print
   `[]`, and the judge `VERDICT` must be `pass` (including the new `PROVENANCE` criterion).
4. Sanity-check the HALT path: with `mw` renamed/unavailable, the run STOPS and names the missing
   prereq instead of producing a partial answer.
