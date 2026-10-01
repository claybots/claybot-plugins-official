# Wrangler → cf

| Task | Wrangler | cf |
|---|---|---|
| Config | `wrangler.toml` / `wrangler.json(c)` | `cloudflare.config.ts` |
| Environments | `[env.<name>]` | `--mode <name>`, branching on `mode` in the config |
| Local dev | `wrangler dev` | `cf dev` (Vite) |
| Deploy | `wrangler deploy` | `cf deploy` |
| Types | `wrangler types` | `cf workers types` |
| D1 query | `wrangler d1 execute <db> --remote` | `cf d1 query <DATABASE_ID> --sql` |
| List D1 | — | `cf d1 list` |
| One secret | `wrangler secret put` | not yet — keep Wrangler, `--name <worker>` |
| Live logs | `wrangler tail <worker>` | not yet — keep Wrangler |

`vars` → `bindings.text`, `kv_namespaces` → `bindings.kv`, `d1_databases` →
`bindings.d1`, `r2_buckets` → `bindings.r2`, `queues.producers` →
`bindings.queue`, `ai` → `bindings.ai`, `vectorize` → `bindings.vectorize`,
`services` → `bindings.worker`; `routes`/`route` → `triggers.fetch`,
`triggers.crons` → `triggers.scheduled`, `queues.consumers` →
`triggers.queue`. Durable Objects, Workflows and Containers need a manual
check.

`cf migrate` keeps Wrangler's bundler unless the project already uses the
Cloudflare Vite plugin. Workers in Python or Rust stay on Wrangler.
