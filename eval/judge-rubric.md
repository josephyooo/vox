# Vox judge rubric

You are grading ONE Vox run (the query + Vox's full output) against the recipe. For each
criterion output `KEY: pass|fail` on its own line, then `VERDICT: pass|fail` (pass only if ALL
critical criteria pass). Critical criteria are marked *.

- ROUTING: did it hit the right sources for the query family, and probe capability first?
- *CITATIONS: is every concrete claim/number backed by a source URL?
- *CORROBORATION: are promoted picks supported by 2+ independent sources (or explicitly flagged single-source)?
- *FABRICATION: is there NO invented data? (absence reported honestly where data was missing)
- TEMPLATE: methodology + ranked table (columns = rubric dimensions) + flags/excluded + one honest pick?
- CONFIDENCE: per-figure confidence marks used (not one global hedge)?
- DEGRADATION: blocked/failed sources listed; thin evidence stated rather than papered over?

Output example:
ROUTING: pass
CITATIONS: pass
CORROBORATION: fail
FABRICATION: pass
TEMPLATE: pass
CONFIDENCE: pass
DEGRADATION: pass
VERDICT: fail
