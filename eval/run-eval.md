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
