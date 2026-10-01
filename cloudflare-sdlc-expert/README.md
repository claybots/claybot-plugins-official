# Cloudflare SDLC expert

A Workers engineer that lives in the [cf CLI](https://developers.cloudflare.com/cf/):
"add a D1-backed `/notes` endpoint to acme/edge" — it plans the change,
writes the code and the `cloudflare.config.ts` bindings, runs the tests,
`cf dev` and `cf deploy --dry-run`, deploys a preview, and opens a pull
request with the preview URL. On every pull request it builds, dry-runs and
previews the Worker and comments with what it found. Production happens
only after you sign off on a deploy card in the console (or say so in words
on a chat platform), and it smoke-tests the deploy afterwards.

It also moves Wrangler projects to `cloudflare.config.ts` with `cf migrate`,
checking binding for binding that nothing was lost, and keeps using
Wrangler for what cf cannot do yet (single secrets, live logs).

**Needs:** a `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`, a
`GITHUB_TOKEN` that can push branches and open pull requests, the
repositories it works on, and their webhook pointed at the agent (Pull
requests, Issue comments). The sandbox needs Node 20+ and npm; cf runs
through `npx`. Recommended runtime: Claude Code (the deploy card and the
Cloudflare docs MCP server).
