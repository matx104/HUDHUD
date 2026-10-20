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
retake is the same take. It opens each take in its own tab a few seconds before its cut (so its
match is already running), brings it to the front on its second, clicks on the beats, starts and
stops OBS, and shows the line to say now, with a countdown to the next, in its terminal. The
browser is Chromium in kiosk mode (no tabs, no address bar), opened from WSL, so it shows on the
Windows desktop for OBS to capture. The studio is reached with the Access service token, added only
to the studio's own requests. The model narrates at its own pace, so the off-air beat waits for the
first line aired on the Scout's facts alone before going back on air.

**Once:**

1. OBS: **Tools → WebSocket Server Settings** → enable (port 4455) → **Show Connect Info** → copy
   the password. In a WSL terminal (yours, not Claude's), so it's never typed into a chat:
   `mkdir -p ~/.config/obs-studio-mcp && read -rs -p 'OBS password: ' p && printf '{"password": "%s"}\n' "$p" > ~/.config/obs-studio-mcp/credentials.json && chmod 600 ~/.config/obs-studio-mcp/credentials.json`
2. Windows PowerShell, as administrator, so WSL can reach OBS (WSL's NAT network is 172.27.240.0/20):
   `New-NetFirewallRule -DisplayName "OBS WebSocket from WSL" -Direction Inbound -Protocol TCP -LocalPort 4455 -RemoteAddress 172.27.240.0/20 -Action Allow`
3. OBS: one scene with a **Display Capture** of the monitor the browser opens on, **Mic/Aux** and
   **Desktop Audio** (the Urdu and Arabic voice). Settings → Video: 1920×1080, 30 fps; Output →
   Recording: MP4 (or MKV, remuxed after).
4. The OBS MCP server (obs-studio-mcp 0.5.1, MIT) is registered for Claude Code as `obs`
   (`~/.local/bin/obs-studio-mcp`, which finds the Windows host itself): run `/mcp` to connect it.
   Claude then checks the scene, the framing (`screenshot_source`) and the audio levels.
5. `.venv/bin/python scripts/director.py --signin`: sign in to the Azure portal in the window
   (yourself), check what the portal's top bar shows, and close it. The profile keeps the sign-in.

**Each take:** `scripts/studio-power on` (the studio warm, no cold start mid-take), then `make doctor`
and `make smoke`; Do Not Disturb on. Then
`.venv/bin/python scripts/director.py` rehearses (nothing recorded), and
`.venv/bin/python scripts/director.py --record` records: OBS starts half a second before the first
frame and stops at 1:50. `--frames DIR` saves each shot as it looks two seconds in, to check a
rehearsal. Each take costs about two cents of models.

## The shots

Spoken pace: about 2.4 words a second. The director prints each line as its shot begins.

| Time | On screen | The director does | Say |
|---|---|---|---|
| 0:00–0:09 | The showcase site: the crest, then the front three | Scrolls to the front three at 0:04 | "AI can commentate a football match. The trouble is, it sounds just as sure when it's wrong. HUDHUD checks every line against the match before it airs." |
| 0:09–0:31 | The studio: seed 21 from 40', 60× live, models, your club and player, xG | Opened at 0:01; the Critic's desk at 0:21, back up at 0:28 | "This is my studio, live on Azure Container Apps. A model on Microsoft Foundry writes each line from facts my code computed. Every line carries its evidence and a receipt, and the Critic's desk shows what it refused, and why." |
| 0:31–0:47 | HUD², the referee's lens: the penalty's call (54') pinned at the foul | Opened at 0:21; the commentator's lens at 0:41, the fan's at 0:44 | "HUD², the referee's lens. A foul in the box: likely a penalty and a yellow, read from the Law and recomputed by the Critic, pinned where it happened. Commentators and fans get lenses of their own." |
| 0:47–1:00 | The studio again | Off air at 0:49; back on once a facts-only line airs | "Now I take the narrator off air. The broadcast keeps going on the Scout's own facts, says so, and brings the commentary back." |
| 1:00–1:12 | Urdu, then Arabic (from 54', voice on) | Voice ticked before each cut | "The same law holds in Urdu and Arabic, on screen and spoken: a translation may not add a number or change a name." |
| 1:12–1:26 | Ask the match: the whole match, the model's checked answer | Verifies the answer at 1:14; asks about the odds at 1:18 | "Ask the match anything, typed or out loud. Code counts every number, the Critic checks the answer, and it's sealed in the match's ledger, so your browser can verify it. And it never helps anyone bet." |
| 1:26–1:40 | Azure: the control-room workbook, then every model call | Opened 12 s ahead (the portal is slow) | "Five agents on Microsoft Agent Framework. Models chosen by evaluation and judged by Foundry's own evaluators. Every call traced, every claim kept on Cosmos DB, and the Critic open to any assistant over MCP and any agent over A2A." |
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
