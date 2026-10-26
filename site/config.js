// The one place the showcase site takes its identity from (the API reads PRODUCT_NAME).
// Chosen 2026-10-17: see brand.md for the decision and project-names.md for the domains.
// index.html's <head> repeats the name and address for crawlers; tests/site keeps them in step.
window.SITE = {
  productName: "HUDHUD",
  productMark: "HUD²", // the short form: monogram, app icon
  siteUrl: "https://hudhud.com.pk/", // canonical address: the project's own domain since 2026-10-19 (was matx104.github.io/HUDHUD, which redirects here)
  repoUrl: "https://github.com/matx104/HUDHUD",
  repoPublic: true, // submitted Oct 24, 2026: the repo is public, the Code links are live
  videoUrl: "https://youtu.be/a9_2oL63PBw", // the judges' cut, 101 seconds
  walkthroughUrl: "https://youtu.be/gQ50gp8kVg4", // the full walkthrough, 4 minutes
  kitUrl: "https://drive.google.com/drive/folders/1gR1Umn8_yD58q-qaiEW2jR1co1S3AO9Y", // the public media kit: video, screenshots, brand (scripts/drive_kit.py)
  studioUrl: "https://studio.hudhud.com.pk/", // the live studio, behind Cloudflare Access (docs/azure.md, "The wall"): the Control room links it
  studioPublic: false, // not for every visitor (2026-10-19): true would put "Watch a live match" on the public pages
  studioJudges: true, // open to the judges (2026-10-26): any @microsoft.com or @premierleague.com address signs in by a one-time code, through Nov 10
  deadline: "2026-10-28T06:59:00Z", // submissions close: Oct 27, 11:59 PM Pacific (official rules §1)
  submitted: "2026-10-24", // this entry went in, Karachi time: three days before the close
  resultsAt: "2026-11-20T08:00:00Z", // winners announced Nov 20 (no hour published): the countdown runs to its start, Pacific
};
