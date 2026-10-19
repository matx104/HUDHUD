// The edge in front of the studio (docs/azure.md, "The wall"). Deploy: scripts/edge.
import { bindings, defineConfig, triggers } from "cf/config";
import * as entrypoint from "./src/index.ts" with { type: "cf-worker" };

export default defineConfig({
	worker: {
		name: "hudhud-edge",
		compatibilityDate: "2026-10-01",
		entrypoint,
		// Only the routes below: no workers.dev or preview address that would skip Access.
		workersDev: false,
		previewUrls: false,
		triggers: [
			triggers.fetch({ pattern: "studio.hudhud.com.pk/*", zone: "hudhud.com.pk" }),
			triggers.fetch({ pattern: "mcp.hudhud.com.pk/*", zone: "hudhud.com.pk" }),
		],
		env: {
			// The studio on Azure Container Apps. Not a secret: it refuses whatever Access didn't sign.
			ORIGIN: bindings.text("https://hudhud-studio.politesand-62c3c2c4.uaenorth.azurecontainerapps.io"),
		},
	},
});
