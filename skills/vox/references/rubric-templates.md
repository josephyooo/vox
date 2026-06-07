# Query-rubric template priors

Starting points, NOT rigid forms. The orchestrator picks the closest family, fills a concrete
rubric (dimensions + source plan + "good" bar), then CONFIRMS with the user before Wave 1 unless
the query already states its criteria.

## Places / food
- Dimensions: rating × review-volume, sentiment, value, [logistics if geo].
- Sources: Reddit + web critics (+ Maps in Phase 2).
- Output: ranked venue table.

## Consumer product (e.g. "best running shoes")
- Dimensions: the attributes that matter (e.g. cushioning, support, durability, price).
- Sources: Reddit (niche subs) + review sites + X.
- Output: ranked model table with attribute columns.

## Media / model sentiment (e.g. "how good is the new Claude model")
- Dimensions: aspects (coding, writing, speed, cost).
- Sources: X + Reddit + HN/web.
- Output: aspect × sentiment with CONSENSUS vs CONTENTION + an overall verdict.

## Company / event (e.g. "SpaceX IPO thoughts")
- Dimensions: bull case / bear case / key facts / sentiment trend.
- Sources: X + web + Reddit.
- Output: balanced brief.

## Behavior
- Query states criteria → echo inferred rubric, proceed (still correctable).
- Query under-specified → propose a concrete rubric, get one quick confirm/adjust.
- No template fits → synthesize a rubric from scratch and confirm.
