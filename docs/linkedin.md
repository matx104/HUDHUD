# The LinkedIn announcement — paste-ready

> Publish day: October 26, 2026 (submission is the 27th). The post links **https://hudhud.com.pk**
> only — the repo goes public with tomorrow's submission and is not linked here.
> Image: `dist/kit/3 Brand kit/linkedin-post-1200x1500.png` (also in the Drive media kit).
> Upload the **demo video natively to the post as well** if it's on YouTube by then — native video
> outperforms links (docs/video.md says the same).

## Tags (in the post body, type them so LinkedIn resolves the mentions)

- **Microsoft**
- **Premier League**
- **Brian Benz** — https://www.linkedin.com/in/brianbenz/

## The post

AI commentary is fluent. Fluency isn't truth — so I built a broadcast that refuses to air a claim it can't prove.

Three weeks. One engineer. Five AI agents. HUDHUD is live: https://hudhud.com.pk

For the Microsoft × Premier League "Inside the Game" hackathon, I built an AI match broadcast with a rule I haven't seen anywhere else: no evidence, no air. As a synthetic football match plays —

▸ The Scout detects what matters: goals, big chances, counterattacks, a high press paying off, momentum swings, control or chaos, the referee's likely call.
▸ The Narrator writes the line (gpt-4.1-mini on Microsoft Foundry, chosen by an evaluation that was committed before it ran).
▸ The Critic recomputes every number from the raw match events. A wrong number, a missing citation, an event from the future — the line goes back with the reasons. Three strikes and it's spiked, on screen.
▸ The Localizer airs it in English, Urdu or Arabic — written and spoken.
▸ And the Orchestrator keeps the broadcast alive when a model fails mid-match: it degrades to cited facts, says so on air, and announces the recovery. The feed never goes dark.

Ask the match a question — typed or spoken — and the model can only get numbers by calling counting tools. The Critic re-checks the answer, and it's sealed into a hash-chained ledger (Certificate Transparency-style Merkle roots) that anyone can verify in their browser. Change one byte of the match's history and it shows.

Under the hood: Microsoft Agent Framework, Foundry (its evaluators judge what aired — groundedness 4.84/5), Azure Container Apps with managed identity and no keys, Azure AI Speech, Cosmos DB audit trail, Application Insights — plus an MCP server and an A2A agent so other assistants can borrow the same Critic.

Three ideas from Brian Benz's Reactor session went straight into the product: a receipt on every answer, let evaluation pick the model, and say plainly what the data can't tell you. That session was worth the watch.

Solo build, from Karachi. 273 tests on every push. The code goes public with tomorrow's submission.

Watch a match, ask it something, try to break the ledger: https://hudhud.com.pk

#InsideTheGame #AI #PremierLeague #Azure #MultiAgent #FootballTech

## The short cut (if you prefer under ~900 characters)

AI commentary is fluent. Fluency isn't truth — so I built a broadcast that refuses to air a claim it can't prove.

HUDHUD: five AI agents commentate a live synthetic football match, and a Critic agent recomputes every number from the raw events before any line airs. Wrong number? Sent back with the reasons. Model dies mid-match? The feed degrades gracefully and says so — never dark. Commentary in English, Urdu and Arabic, written and spoken. Ask the match anything — every answer tool-checked, sealed in a hash-chained ledger the browser verifies.

Microsoft Agent Framework · Foundry · Azure Container Apps · MCP · A2A. Solo build, from Karachi, for the Microsoft × Premier League "Inside the Game" hackathon.

https://hudhud.com.pk

## First comment (post immediately after)

The media kit — the 101-second demo video, screenshots, the brand sheet and the deliverables report (every ask of the challenge, met and linked to its evidence):
https://drive.google.com/drive/folders/1gR1Umn8_yD58q-qaiEW2jR1co1S3AO9Y

## Notes

- The first two lines must carry the hook: LinkedIn truncates at roughly 200 characters.
- Tag the three names as mentions (start typing @ and pick the page) — plain text does not notify.
- The claim on the card is real: it airs on the site's home page, from synthetic match seed 7 —
  first draft refused (it cited an event that hadn't happened), second verified. Examiners can
  check it.
- Reply to every comment in the first two hours; the algorithm carries the post on replies.
