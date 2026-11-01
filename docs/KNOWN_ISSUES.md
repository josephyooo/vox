# Known issues

Open defects from live runs. Delete an entry when its fix lands.

## vox-browser
- Maps' review Sort opens a sign-in modal in a signed-out profile, so newest reviews are unreadable there. Use a signed-in profile for recency, or disclose the gap. Full hours can sit behind "See more hours".
- The playbook omits these tool responses: `Navigation to this domain is not allowed`, which also drops the remaining `browser_batch` steps; `Permission denied for reading page content on this domain`; `[BLOCKED: Cookie/query string data]` on JavaScript output; `[TRUNCATED]` on long JavaScript output.
- Clicking a search result can open a new tab, and later batched steps then run on the old tab.

## vox-web
- WebFetch refuses web.archive.org. Send snapshot reads in `antibot-ladder.md` to curl.
- `SKILL.md` treats WebSearch snippets as data, but WebSearch returns links plus model-written prose that can mangle facts. Cap those facts at `~`.
- WebFetch's summarizing model can miss data that curl shows on the same page, such as phone and hours.

## vox-reddit
- `reddit-cli browse <nonexistent sub>` prints rows with empty fields and no permalink. Treat them as "no such sub".
- Name search misses venues mentioned only in comments. Drill threads and grep them.
- `reddit-cli comments` has no per-comment permalinks and gives relative ages only.

## vox-x
- `bird search` with an exact phrase containing `&` returns `[]` with exit 0, which reads as no signal. Quote the part before `&` instead.
- `bird` `text` holds raw HTML entities. Unescape before quoting.
- The allowed-command list needs `bird about <handle>` for location checks, and `bird read <id> --json-full` for expanded links.
