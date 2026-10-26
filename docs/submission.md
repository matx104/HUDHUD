# The submission: the text, ready to paste

Drafted 2026-10-21 for Innovation Studio and **submitted on Oct 24 PKT**, three days before
submissions close (**Oct 27, 11:59 PM PT; Oct 28, 11:59 AM PKT**). Every public word is first person
singular (goals.md). The claims here were checked against the repo on the day.

## Title

HUDHUD: AI match commentary that proves every claim

## Tagline (one line)

Five agents turn a live synthetic match into commentary, recaps and answers in English, Urdu and
Arabic, and a Critic recomputes every number from the raw events before anything airs.

## Category

Grand Prize, and **Best Use of Microsoft Foundry** as the category prize (the rules allow one of
each, §4.2 and §8; goals.md).

## The pitch: what I built, the stack, the problem

**The problem.** Football broadcasts run on numbers, and more and more of the words around them
will be written by AI. A model that invents a statistic on air costs a broadcaster its credibility
in one line, and a commentary system that goes silent when a model times out is not one a studio can
put on air.

**What I built.** HUDHUD is AI match commentary that proves every claim before it airs. Five agents
work a live synthetic match. The Scout detects what matters on the hot path, with no model:
goals, big chances by xG, great passes, counterattacks, a high press paying off, swings in momentum,
a match broken open end to end (control or chaos), and fouls with the referee's likely call under
the competition's strictness. The Narrator writes the line on Microsoft Foundry from a fact sheet
code computed. The Critic recomputes every number from the raw events and refuses what it can't
prove, live on screen with the reason, and the line is rewritten or spiked. The Localizer airs it
in English, Urdu or Arabic, for a casual fan or an analyst, on screen and spoken by Azure AI
Speech. The Orchestrator keeps the broadcast on air when a model fails: it drops to the Scout's own
cited facts, says so, and recovers. Every line carries the events it stands on and a receipt (who
wrote it, what it cost, what was checked).

Viewers make it theirs: a club, a player, one number to follow. At full time the match writes its own
recap, every line checked. Anyone can ask the match a question, typed or spoken, and the answer
stands on the Scout's counting tools and is checked by the Critic before it shows. HUD² shows the same
match through the referee's, the commentator's or the fan's lens. Every event, line, refusal and
answer is sealed minute by minute into a ledger chained by hashes, which the browser verifies. It
never predicts results or shows odds, and a betting question gets fixed words before any model
reads it.

**The stack.**
- **Microsoft Agent Framework:** the warm path (Narrator → Critic → Localizer, with a rewrite
  edge) as a workflow; the Critic also serves other agents over A2A.
- **Microsoft Foundry:** gpt-4.1-mini writes the lines and gpt-5-mini stands by, chosen by an
  evaluation committed before it ran (ADR 0005); Foundry's evaluators judge the lines that aired;
  the model calls show in Foundry's tracing.
- **Azure Container Apps:** the studio, one container, signed in to every service with one managed
  identity and no keys; images in Azure Container Registry.
- **Azure AI Speech** (neural voices in English, Urdu and Arabic) and **Azure AI Content Safety**
  (Prompt Shields on every question).
- **Azure Cosmos DB** (free tier): the audit trail of every claim, verdict and cue.
- **Application Insights and Log Analytics:** traces of every match and alert, and a workbook.
- **MCP:** the Critic as a read-only MCP server (stdio and streamable HTTP); the **Azure MCP
  Server** and **GitHub Copilot agent mode** in the build; GitHub Actions run every test on every
  push.

**Why it matters.** The same law (code counts, models write, nothing airs unproven) carries from
commentary to the referee's room: the roadmap ends at an AI fourth official that advises the
referee and shows its evidence, and today's Critic, ref's call and ledger are its first steps.

## Links

- Demo video (under 2:00): https://youtu.be/a9_2oL63PBw
- Full walkthrough (4 minutes): https://youtu.be/gQ50gp8kVg4
- Code: https://github.com/matx104/HUDHUD
- Showcase site, with replays of a match recorded from the live studio: https://hudhud.com.pk/
- A recap the match wrote itself: https://hudhud.com.pk/recap/seed-21.html
- Media kit (video, screenshots, brand): https://drive.google.com/drive/folders/1gR1Umn8_yD58q-qaiEW2jR1co1S3AO9Y

## Testing instructions

**Judges: the live studio is open to you** (added 2026-10-26; docs/azure.md, "The wall"). Open
https://studio.hudhud.com.pk/ and sign in with your @microsoft.com email address: Cloudflare Access
emails a one-time code, with no password and no account. Pick a match and press Kick off: the
Foundry models narrate it live, the Critic's refusals show as they happen, "Stress-test the Critic"
corrupts drafts on purpose, and "Take the narrator off air" shows the broadcast degrade and recover.
HUD² is at /hud, Ask the match at /ask. It stays open through November 10.

For everyone else the live studio is private. Three ways to see HUDHUD work, none of which needs an
account:

1. **In the browser, nothing to install:** https://hudhud.com.pk/#/screens. "Replay the studio",
   "Replay HUD²" and "Ask the recorded match" run the studio's own pages and code on a match
   recorded from the live studio on October 20: the lines, the Critic's refusals and the ledger are
   real, and the ledger verifies in your browser.
2. **The whole studio on your machine, no Azure:** with Python 3.13,
   `git clone https://github.com/matx104/HUDHUD && cd HUDHUD && make setup && make studio-offline`,
   then open http://localhost:8091. Pick a match and press Kick off: the offline narrator writes the
   lines, and "Stress-test the Critic" corrupts one draft in four so you can watch the Critic refuse
   them. "Take the narrator off air" shows the broadcast degrade and recover. HUD² is at /hud, Ask
   the match at /ask.
3. **The tests:** `make test` (Python, and the site and studio with Node 22), `make eval` (the Scout's momentum calls scored
   against the generator's hidden ground truth on unseen seeds).

With Azure: `docs/azure.md` sets up Foundry, and `make studio` runs the same studio narrated by the
Foundry models.

## Before pressing Submit (the owner's steps)

- [x] The video is on YouTube (public or unlisted), under 2:00, no third-party marks or music;
      its URL is in **Links** above and in `site/config.js` (`videoUrl`): the judges' cut, 101 s
- [x] The repo is public on GitHub, and `site/config.js` has `repoPublic: true` (the site's Code
      links work only once the repo is public)
- [x] https://hudhud.com.pk/#/screens replays play in a private window (re-checked 2026-10-25 in a
      fresh browser: lines air, the Critic's refusals show)
- [x] A fresh clone passes `make setup && make test` and `make studio-offline` serves a match
      (re-checked 2026-10-25: 273 tests pass; seed 21 streams lines, shots and ledger blocks)
- [x] Submitted on Innovation Studio on Oct 24 PKT, three days early, with this page's text
- [ ] The judges' sign-in (the first paragraph of **Testing instructions**) pasted into the
      submission on Innovation Studio, if it can still be edited before the close (Oct 28, 11:59 AM
      PKT); the site's judges' door and the README say it either way
