// The one place the showcase site takes its identity from (the API reads PRODUCT_NAME).
// Chosen 2026-10-17: see brand.md for the decision and project-names.md for the domains.
// index.html's <head> repeats the name and address for crawlers; tests/site keeps them in step.
window.SITE = {
  productName: "HUDHUD",
  productMark: "HUD²", // the short form: monogram, app icon
  siteUrl: "https://hudhud.com.pk/", // canonical address: the project's own domain since 2026-10-19 (was matx104.github.io/HUDHUD, which redirects here)
  repoUrl: "https://github.com/matx104/HUDHUD",
  repoPublic: false, // flip at submission: shows the Code links (a private repo 404s for visitors)
  videoUrl: "https://youtu.be/a9_2oL63PBw", // the judges' cut, 101 seconds
  walkthroughUrl: "https://youtu.be/gQ50gp8kVg4", // the full walkthrough, 4 minutes
  kitUrl: "https://drive.google.com/drive/folders/1gR1Umn8_yD58q-qaiEW2jR1co1S3AO9Y", // the public media kit: video, screenshots, brand (scripts/drive_kit.py)
  studioUrl: "https://studio.hudhud.com.pk/", // the live studio, behind Cloudflare Access (docs/azure.md, "The wall"): the Control room links it
  studioPublic: false, // owner-only (2026-10-19): true would put "Watch a live match" on the public pages
  deadline: "2026-10-28T06:59:00Z", // submissions close: Oct 27, 11:59 PM Pacific (official rules §1)
};
