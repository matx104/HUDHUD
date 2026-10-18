// The one place the showcase site takes its identity from (the API reads PRODUCT_NAME).
// Chosen 2026-10-17: see brand.md for the decision and project-names.md for the domains.
// index.html's <head> repeats the name and address for crawlers; tests/site keeps them in step.
window.SITE = {
  productName: "HUDHUD",
  productMark: "HUD²", // the short form: monogram, app icon
  siteUrl: "https://matx104.github.io/HUDHUD/", // canonical address; change with the domain
  repoUrl: "https://github.com/matx104/HUDHUD",
  repoPublic: false, // flip at submission: shows the Code links (a private repo 404s for visitors)
  videoUrl: null, // the 110-second demo, once it has a public URL
  studioUrl: "https://hudhud-studio.politesand-62c3c2c4.uaenorth.azurecontainerapps.io/", // the live studio on Azure Container Apps
  deadline: "2026-10-28T06:59:00Z", // submissions close: Oct 27, 11:59 PM Pacific (official rules §1)
};
