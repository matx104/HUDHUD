// Carries each request Cloudflare Access let in on to the studio on Azure, and the answer back.
//
// Why a Worker: the studio's express Container Apps environment takes no custom domain, and only
// Enterprise plans can rewrite the Host header with a rule, so a plain proxied record can't reach
// it. Access runs before this Worker and adds its signed token (Cf-Access-Jwt-Assertion), which
// the studio checks (court/server.py, AccessOnly). Streams pass straight through, so a match's
// Server-Sent Events arrive as they happen.
//
//   studio.hudhud.com.pk/...  ->  <origin>/...
//   mcp.hudhud.com.pk/...     ->  <origin>/mcp/...   (the Critic's MCP endpoint)
import { env } from "cloudflare:workers";

const MCP = "/mcp";

export default {
	async fetch(request) {
		const url = new URL(request.url);
		const mcp = url.hostname.startsWith("mcp.");
		const upstream = new URL(env.ORIGIN);
		upstream.pathname = mcp ? MCP + url.pathname : url.pathname;
		upstream.search = url.search;

		const headers = new Headers(request.headers);
		headers.delete("Host"); // the fetch names Azure
		headers.delete("Cookie"); // Access's session cookie stays at the edge; the studio sets none
		const response = await fetch(upstream, {
			method: request.method,
			headers,
			body: request.body,
			redirect: "manual",
		});

		// A redirect from the studio names its Azure address: send the viewer back to this one.
		const location = response.headers.get("Location");
		if (!location) return response;
		const target = new URL(location, upstream);
		if (target.host !== upstream.host) return response;
		const path = mcp && target.pathname.startsWith(MCP) ? target.pathname.slice(MCP.length) || "/" : target.pathname;
		const moved = new Response(response.body, response);
		moved.headers.set("Location", new URL(path + target.search, url.origin).href);
		return moved;
	},
} satisfies ExportedHandler;
