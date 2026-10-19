# The demo video: 110 seconds

The hackathon's video is the judges' first look, and they need not watch past two minutes. This is
the kit for recording it: the rules, the checklist, the shots with their voiceover, and the
description. The Monarch records and narrates; everything on screen is live, nothing staged.

## The rules that bind it (task.md, brand.md)

- **Under 2:00, hard.** I aim for 1:50, so a slow take still fits.
- **No third-party trademarks or logos**: no league, club or broadcaster marks on screen or in the
  voiceover's visuals. Every club and player in HUDHUD is invented, so the studio is safe as it is.
  Keep browser tabs, bookmarks and the taskbar out of frame.
- **No copyrighted music.** Voice only, or royalty-free audio you have the licence for.
- **A public URL on YouTube, Vimeo, Facebook Video or Youku** (official rules §4, Submission
  Requirements). Those four are the only hosts the rules name: a Google Drive link does not count
  for the submission. An unlisted YouTube video works (it never shows on the channel YouTube makes
  for the upload), and so does a free Vimeo account.
- **The master copy lives on Google Drive**, in the public media kit:
  `.venv/bin/python scripts/drive_kit.py --video demo.mp4` uploads it to "1 Demo video" and prints
  its link. Put the link in `site/config.js` (`videoUrl`) and the site shows it on the home page.
  Drive throttles a file that many people stream at once, so for LinkedIn upload the video to the
  post itself as well: native video plays inline there and reaches more people than a link.

## Before recording (10 minutes)

1. `scripts/studio-power on`: the studio warm, no cold start mid-take.
2. `make doctor`: all checks green. `make smoke`: the live studio streams a match.
3. Sign in to the Azure portal in the recording browser, for the control-room shots.
4. Sign in to the studio (studio.hudhud.com.pk: a code to your email), then open the takes from
   the showcase site's Control room page (`#/control`, "The live studio"): **Take: the whole
   story**, then **Take: Urdu** and **Take: Arabic** (seed 21 from 54', 30 times live, models,
   stress test on). Each starts the moment it opens.
5. Browser window 1920×1080, zoom 100–110%, dark OS theme. Close everything else. Do not disturb on.
6. Record with OBS (or any recorder) at 1080p, 30 fps; record voice separately if you prefer, and
   lay it over.

**Take: the whole story** (Control room, "The live studio") starts seed 21 at 45', 60 times live,
narrated by the Foundry models, stress test on, Saltmarsh Rovers as your club, Adem Rosmere as your
player, xG as your one number, the referee at standard. Tick **Hear the commentary** before it
starts. In about 50 seconds it gives: big chances (48', 53', 73'), the ref's call on the penalty
(54'), two goals (55', 56'), momentum swings (62', 78'), the high press (66', 77', 86') and a
second ref's call (90'); the stress test corrupts about one draft in four, so the Critic's desk
gets red cards. At full time the recap is offered, and Ask the match stays open.

## The shots

Spoken pace: about 2.4 words a second. The voiceover below is about 255 words.

| Time | On screen | Do | Say |
|---|---|---|---|
| 0:00–0:10 | Showcase site: the crest and the wordmark, then "In plain words" | Scroll slowly | "AI can commentate a football match. The trouble is, it sounds just as sure when it's wrong. HUDHUD checks every line against the match before it airs." |
| 0:10–0:34 | **Take: the whole story**, voice on | Let it run from 45' | "This is my studio, on Azure Container Apps. A model on Microsoft Foundry writes each line from facts my code computed, and Azure AI Speech reads it aloud. I made it mine: my club's moments come first, my player gets a live card, and xG ticks for both sides. Every cue carries its evidence and a receipt." |
| 0:34–0:50 | The ref's call at 54', then the Critic's desk as a red card lands | Point at the yellow card; open a red card's reason | "A foul in the box: the likely call, a penalty and a yellow, read from the Law at the strictness I chose, and recomputed by the Critic. Here it refused a draft that cited an event that hadn't happened yet, said why, and the rewrite aired." |
| 0:50–1:04 | "Take the narrator off air", then back | Press at about 70'; again after the 73' cue | "Now I take the narrator off air. The Orchestrator keeps the broadcast going on the Scout's own facts, says so, and brings commentary back when the narrator returns." |
| 1:04–1:14 | **Take: Urdu**, voice on; then **Take: Arabic** | Let one line be spoken in each | "The same law holds in Urdu and Arabic, on screen and spoken: a translation may not add a number or change a name." |
| 1:14–1:24 | Full time: "Read the recap", then Ask the match: "Who has been the better side, by the numbers?" | Open the recap; then tap the question and open "What the tools counted" | "At full time the match writes its recap and answers my questions, every number checked by the Critic first." |
| 1:24–1:46 | Control room: the workbook; Foundry's tracing and its evaluation run; the studio's sign-in | Scroll the tiles; open the evaluation | "Five agents on Microsoft Agent Framework. Models chosen by evaluation and judged again by Foundry's own evaluators. Every call traced in Foundry and Application Insights, every claim in an audit trail on Cosmos DB, and the studio private behind its own wall. The Critic is an MCP tool for any assistant and an A2A agent for any agent." |
| 1:46–1:52 | Showcase home, the crest | Hold | "HUDHUD. Built by one engineer. Every call comes with its evidence." |

## The description (the video's page, and the submission)

> HUDHUD: AI football commentary that shows its working. Five agents on Microsoft Agent Framework
> commentate a synthetic match; a Critic agent recomputes every number from the raw events before a
> line airs, refuses what it can't prove, and sends it back for a rewrite. Models on Microsoft
> Foundry (chosen by evaluation), the studio on Azure Container Apps, an audit trail on Azure Cosmos
> DB, traces in Application Insights, and the Critic as an MCP server and an A2A agent. Viewers ask
> the match questions, typed or out loud, and every answer is checked the same way. English, Urdu
> and Arabic.
> Every club, player and match is invented; synthetic data only.
>
> About it: https://hudhud.com.pk/
> Video, screenshots and brand kit: https://kit.hudhud.com.pk/
> Run it yourself: https://github.com/matx104/HUDHUD (make setup, then make studio-offline)
> Built for Inside the Game: Developer Hackathon (October 2026). An independent entry.
