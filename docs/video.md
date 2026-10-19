# The demo video: 110 seconds

The hackathon's video is the judges' first look, and they need not watch past two minutes. This is
the kit for recording it: the rules, the checklist, the shots with their voiceover, and the
description. The Monarch records and narrates; everything on screen is live, nothing staged.

## The rules that bind it (task.md, brand.md)

- **Under 2:00, hard.** We aim for 1:50, so a slow take still fits.
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
4. Open the takes from the showcase site's Control room page (`#/control`, "The live studio"):
   **Take: English**, **Take: Urdu**, **Take: Arabic**. Each starts seed 21 at 54', 30 times live
   speed, narrated by the Foundry models, with the stress test on, the moment it opens.
5. Browser window 1920×1080, zoom 100–110%, dark OS theme. Close everything else. Do not disturb on.
6. Record with OBS (or any recorder) at 1080p, 30 fps; record voice separately if you prefer, and
   lay it over.

Seed 21 from 54' gives, in about 70 seconds: two goals (55', 56'), a momentum swing (62'), a big
chance (73'), and a second swing (78'). The stress test corrupts about one draft in four, so the
Critic's desk gets red cards to show.

## The shots

Spoken pace: about 2.4 words a second. The voiceover below is about 250 words.

| Time | On screen | Do | Say |
|---|---|---|---|
| 0:00–0:14 | Showcase site, home, then "In plain words" | Scroll slowly | "AI can already commentate a football match. The trouble is, it sounds just as sure when it's wrong, and on air one wrong number costs a broadcaster its viewers' trust. HUDHUD fixes that: every line is checked against the match before it airs." |
| 0:14–0:40 | **Take: English** (the studio) | Let it run from 54' | "This is the studio, live on Azure Container Apps. A synthetic match streams in. The Scout spots the moments, and a model on Microsoft Foundry writes each line from facts our own code computed. Every cue shows its evidence, tags its players, and carries a receipt: who wrote it, how many numbers were checked, how long it took, and what it cost: a fraction of a cent." |
| 0:40–1:05 | The Critic's desk, as a red card lands | Point at the card; open its reason | "Here a draft cited an event that hadn't happened yet. The Critic recomputes every claim from the raw events, so it refused it, said exactly why, and sent it back. The rewrite aired seconds later. Nothing unverified reaches the screen." |
| 1:05–1:20 | The studio, then "Take the narrator off air" | Press it at about 70'; press again after the 73' cue | "Now I take the narrator off air. The Orchestrator keeps the broadcast going with the Scout's own facts, says so on screen, and brings full commentary back the moment the narrator returns." |
| 1:20–1:32 | **Take: Urdu**, then **Take: Arabic** | A cue in each; open "In English" once | "The same law holds in Urdu and Arabic: a translation may not state a number the checked line doesn't, or change a name." |
| 1:32–1:48 | Control room: the HUDHUD workbook, then the showcase site's How it works | Scroll the workbook's headline tiles | "Five agents on Microsoft Agent Framework. Models chosen by evaluation, on Foundry. Every claim in an audit trail on Cosmos DB, every step traced in Application Insights, and the Critic itself an MCP tool any assistant can use." |
| 1:48–1:52 | Showcase home, the hero line | Hold | "HUDHUD. Every call comes with its evidence." |

## The description (the video's page, and the submission)

> HUDHUD: AI football commentary that shows its working. Five agents on Microsoft Agent Framework
> commentate a synthetic match; a Critic agent recomputes every number from the raw events before a
> line airs, refuses what it can't prove, and sends it back for a rewrite. Models on Microsoft
> Foundry (chosen by evaluation), the studio on Azure Container Apps, an audit trail on Azure Cosmos
> DB, traces in Application Insights, and the Critic as an MCP server. English, Urdu and Arabic.
> Every club, player and match is invented; synthetic data only.
>
> Try it: https://studio.hudhud.com.pk/
> About it: https://hudhud.com.pk/
> Video, screenshots and brand kit: https://drive.google.com/drive/folders/1gR1Umn8_yD58q-qaiEW2jR1co1S3AO9Y
> Built for Inside the Game: Developer Hackathon (October 2026). An independent entry.
