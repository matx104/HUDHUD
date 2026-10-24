# The demo video: the judges' cut, 101 seconds

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
  for the submission. It goes on the Monarch's channel, MATX104
  (https://www.youtube.com/@monarch-_-mat). Public or unlisted both work: an unlisted video plays
  for anyone with the link but never shows on the channel.
- **The master copy lives on Google Drive**, in the public media kit:
  `.venv/bin/python scripts/drive_kit.py --video demo.mp4` uploads it to "1 Demo video" and prints
  its link. Put the link in `site/config.js` (`videoUrl`) and the site shows it on the home page.
  Drive throttles a file that many people stream at once, so for LinkedIn upload the video to the
  post itself as well: native video plays inline there and reaches more people than a link.

## How it's recorded: the director

`scripts/director.py` drives the whole video on one clock, so every beat lands on its line and a
retake is the same take. It plays the take in the owner's own Chrome on Windows, the one already
signed in to the Azure portal, over the Chrome DevTools Protocol: the owner turns remote debugging on
at `chrome://inspect/#remote-debugging`, and Chrome asks them to allow the connection. The director
touches only the full-screen window it opens and the tabs in it. Chrome listens on Windows'
loopback, which WSL can't reach, so the connection goes through PowerShell on the Windows side; no
port is opened.

Each take opens in its own tab a few seconds before its cut (so its match is already running), comes
to the front on its second, and gets its clicks on the beats; OBS starts and stops with the video.
The two Azure pages draw only on screen, so they're opened and drawn before the clock starts. A tab
is heard only while it's on screen. The studio is reached with the Access service token, added only
to the studio's own requests. The model narrates at its own pace, so the off-air beat waits for the
first line aired on the Scout's facts alone before going back on air.

**Once:**

1. OBS: **Tools → WebSocket Server Settings** → enable (port 4455). Its password goes in the
   repo's `.env` as `OBS_MCP_PASSWORD` (gitignored; see `.env.example`), where the director and the
   OBS MCP server both read it.
2. Windows PowerShell, as administrator, so WSL can reach OBS (WSL's NAT network is 172.27.240.0/20):
   `New-NetFirewallRule -DisplayName "OBS WebSocket from WSL" -Direction Inbound -Protocol TCP -LocalPort 4455 -RemoteAddress 172.27.240.0/20 -Action Allow`
3. OBS: one scene with a **Display Capture** of the screen (cursor hidden) and **Desktop Audio**
   (the studio's Urdu and Arabic voice); the mic muted, since the voiceover is added afterwards.
   Settings → Video: 1920×1080.
4. Chrome: `chrome://inspect/#remote-debugging`, allow remote debugging. Turn it off after.

**Each take:** `scripts/studio-power on` (the studio warm, no cold start mid-take), then `make doctor`
and `make smoke`; Do Not Disturb on, Spotify paused. Then
`.venv/bin/python scripts/director.py --record --control FILE`: allow the connection in Chrome,
close the "controlled by automated test software" bar with its ×, move the mouse to the right edge
and leave the machine alone for three minutes. Writing `record`, `rehearse` or `quit` to FILE runs
the next take on the same connection. `--frames DIR` saves each shot as it looks two and six seconds
in, from OBS; `--headless` tests the shots in a local Chromium at the owner's screen size.

**Finishing:** `.venv/bin/python scripts/video_post.py TAKE.mp4` makes `dist/video/hudhud-demo.mp4`:
the voiceover read by Azure AI Speech (en-US-AndrewMultilingualNeural, a different voice from the
studio's commentary), each sentence placed on its shot and burned in as a caption under the shot's
title, for anyone watching with the sound off; the frames where Chrome hadn't yet drawn a tab just
brought forward held on the frame before; the take's own sound ducked under the narration, the whole
at −16 LUFS. `--swap 86=AZURE.mp4` lays a shot recorded on its own over the take. Each take costs
about two cents of models, and the voiceover about a cent.

## The shots

Spoken pace: about 2.6 words a second; `scripts/video_post.py --plan` prints where each sentence falls.

| Time | On screen | The director does | Say |
|---|---|---|---|
| 0:00–0:09 | The showcase site: the crest, then the front three | Scrolls to the front three at 0:04 | "AI can commentate a football match. The trouble is, it sounds just as sure when it's wrong. HUDHUD checks every line against the match before it airs." |
| 0:09–0:31 | The studio: seed 21 from 40', 60× live, models, your club and player, xG | Opened at 0:01; the Critic's desk at 0:21, back up at 0:28 | "This is my studio, live on Azure Container Apps. A model on Microsoft Foundry writes each line from facts my code computed. Every line carries its evidence and a receipt, and the Critic's desk shows what it refused, and why." |
| 0:31–0:47 | HUD², the referee's lens: the penalty's call (54') pinned at the foul | Opened at 0:16; the commentator's lens at 0:41, the fan's at 0:44 | "HUD², the referee's lens. A foul in the box: likely a penalty and a yellow, read from the Law and recomputed by the Critic, pinned where it happened. Commentators and fans get lenses of their own." |
| 0:47–1:00 | The studio again | Off air at 0:49; back on once a facts-only line airs | "Now I take the narrator off air. The broadcast keeps going on the Scout's own facts, says so, and brings the commentary back." |
| 1:00–1:12 | Urdu, then Arabic (from 54', voice on) | Voice ticked just after each cut: it reads the line on air | "The same law holds in Urdu and Arabic, on screen and spoken: a translation may not add a number or change a name." |
| 1:12–1:26 | Ask the match: the whole match, the model's checked answer | Verifies the answer at 1:14; asks about the odds at 1:18 | "Ask the match anything, typed or out loud. Code counts every number, the Critic checks the answer, and it's sealed in the match's ledger, so your browser can verify it. And it never helps anyone bet." |
| 1:26–1:40 | Azure: the control-room workbook, then every model call | Drawn before the take starts (the portal draws only on screen) | "Five agents on Microsoft Agent Framework. Models chosen by evaluation and judged by Foundry's own evaluators. Every call traced, every claim kept on Cosmos DB, and the Critic open to any assistant over MCP and any agent over A2A." |
| 1:40–1:44 | The site's match ledger, verified in the browser | Verify at 1:41 | (the line above runs on) |
| 1:44–1:50 | The site's team sheet: the chapters in formation | Opens it at 1:45 | "HUDHUD. Built by one engineer. Every call comes with its evidence." |

## The description (the video's page, and the submission)

> HUDHUD: AI football commentary that shows its working. Five agents on Microsoft Agent Framework
> commentate a synthetic match; a Critic agent recomputes every number from the raw events before a
> line airs, refuses what it can't prove, and sends it back for a rewrite. Models on Microsoft
> Foundry (chosen by evaluation), the studio on Azure Container Apps, an audit trail on Azure Cosmos
> DB, traces in Application Insights, and the Critic as an MCP server and an A2A agent. Viewers ask
> the match questions, typed or out loud, and every answer is checked the same way. HUD² shows the
> match through the referee's, the commentator's or the fan's lens, every checked line pinned where
> it happened. Every match keeps a ledger chained by hashes, so its history can't be quietly
> changed. It never predicts a result or shows odds. English, Urdu and Arabic.
> Every club, player and match is invented; synthetic data only.
>
> About it: https://hudhud.com.pk/
> Video, screenshots and brand kit: https://kit.hudhud.com.pk/
> Run it yourself: https://github.com/matx104/HUDHUD (make setup, then make studio-offline)
> Built for Inside the Game: Developer Hackathon (October 2026). An independent entry.
