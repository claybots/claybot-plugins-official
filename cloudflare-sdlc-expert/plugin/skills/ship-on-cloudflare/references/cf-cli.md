# The cf CLI

cf is Cloudflare's agent-first CLI: every Cloudflare API operation as a
command, generated from the OpenAPI schema, plus project commands for
Workers. Docs: https://developers.cloudflare.com/cf/ (the cloudflare-docs MCP
server searches them). It is in open beta; Wrangler stays supported beside
it.

## Auth

- `CLOUDFLARE_API_TOKEN` takes priority over any stored login. There is no
  Wrangler fallback.
- `CLOUDFLARE_ACCOUNT_ID` selects the account; `CLOUDFLARE_ZONE_ID` the zone
  when `--zone` is not passed.
- `cf whoami` confirms access. `cf auth login` is browser OAuth — not for an
  agent.
- A 401 means the token is missing or wrong; a 403 means it lacks a
  permission — name the permission the command needs.

## Output

- Results are JSON on stdout (arrays for lists); messages, the selected zone
  and errors go to stderr. Parse stdout with `jq`; never scrape stderr.
- A destructive change may print nothing. Raw content (an R2 object, an
  image) comes out unchanged.
- A destructive command run non-interactively without `--force` prints
  `Aborted.` — that is cf refusing, not an error to work around.

## Finding a command

```
npx cf cli search "create D1 database"   # up to five matches, JSON
npx cf schema d1 create                  # parameters, types, required
npx cf d1 create --name my-db --dry-run  # the request, not sent
```

Path parameters: the last one is positional, earlier ones are required
flags; the account and zone are always global. Any string body flag takes
`@path/to/file`.

## Global flags

| Flag | |
|---|---|
| `--zone`, `-z` | Zone ID or domain |
| `--mode`, `-m` | Mode `cloudflare.config.ts` is evaluated with |
| `--local` | Act on local Miniflare state (KV keys, D1) |
| `--persist-to` | Local state directory |
| `--dry-run` | Show the request without sending it |
| `--force`, `-f` | Skip confirmation on destructive operations — owner-named resources only |
| `--quiet`, `-q` | Less output |
| `--profile` | Auth profile |

## Project commands

| | |
|---|---|
| `cf init <dir> [--package-manager npm]` | New Worker (Vite, `cloudflare.config.ts`, `src/index.ts`); `cf init .` configures an existing app |
| `cf dev` | Local dev server on Vite, `http://localhost:5173/` by default, with HMR |
| `cf build` | Build Output to `.cloudflare/output/v0/` |
| `cf deploy` | Build and deploy; `--prebuilt` deploys the existing Build Output; `--dry-run` validates without uploading; `--mode`; `--worker <name>` picks one of several |
| `cf previews deploy` | Preview deployment |
| `cf workers types` | Binding and runtime types into `.cloudflare/types/` |
| `cf workers check` | Local checks |
| `cf migrate [--dry-run]` | Wrangler config → `cloudflare.config.ts` |
| `cf d1 list` · `cf d1 query <DATABASE_ID> --sql "<sql>"` | D1 |
| `cf zones list` | Zones the token can see |

Anything not listed: `cf cli search`. Do not guess a command or flag.

## Not in cf yet — use Wrangler

- Setting a single secret: `npx wrangler secret put <NAME> --name <worker>`
  (the owner runs it; you never hold the value).
- Live logs: `npx wrangler tail <worker>`.
- Workers in Python or Rust, or built with esbuild rather than Vite: cf hands
  them to Wrangler.

Wrangler does not read `cloudflare.config.ts`, so pass `--name <worker>` to
any Wrangler command in a cf project.

## CI

`npm i -D cf`, store `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` as
secrets, then `npx cf build` and `npx cf deploy --prebuilt --mode production`
(`--dry-run` needs no credentials). `CF_SEND_TELEMETRY=false` turns
telemetry off.
