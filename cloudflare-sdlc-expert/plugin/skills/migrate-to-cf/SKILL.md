---
name: migrate-to-cf
description: Move a Wrangler Workers project to the cf CLI and cloudflare.config.ts with cf migrate, prove nothing was lost binding by binding, and open a pull request. Use when someone asks to migrate, convert or move a project from Wrangler to cf.
---

# Migrate a Wrangler project to cf

`references/mapping.md` maps Wrangler's keys and commands onto cf's. A
migration never deploys to production; it ends at a pull request with a
preview.

## 1. Inventory

Read the Wrangler config (`wrangler.toml`, `wrangler.json` or
`wrangler.jsonc`) and write down, per environment (top level is one):
the Worker name, `main`, `compatibility_date` and flags, every binding (kind,
binding name, resource name or id), routes, crons, queue consumers, Durable
Objects and their migrations, Workflows, Containers, and the build (custom
`build.command`, esbuild, the Cloudflare Vite plugin). Also note the scripts
in `package.json` and CI workflows that call `wrangler`.

Stop and say why when the Worker is Python or Rust (cf hands those to
Wrangler) — there is nothing to migrate yet.

## 2. Baseline

On the default branch's head: install, run the tests, and
`npx wrangler deploy --dry-run --outdir .wrangler-baseline` for each
environment. Keep the output; it is what step 5 compares against.

## 3. Migrate

Branch `cf/migrate-to-cf`. Run `npx --yes cf migrate --dry-run`, read what it
would write, then `npx --yes cf migrate`. Add `cf` to devDependencies
(`npm i -D cf`).

## 4. Fix up

- Durable Objects, Workflows and Containers: check each against the docs
  (cloudflare-docs MCP) and fix the config by hand.
- Environments became modes: make sure every per-environment resource name
  or id is chosen by `mode`, as `../ship-on-cloudflare/references/config.md`
  shows.
- Replace `wrangler dev`/`deploy`/`types` in `package.json` scripts and CI
  with the cf commands; CI deploys with `npx cf build` and `npx cf deploy
  --prebuilt --mode <mode>`.
- Keep Wrangler only for single secrets and `tail`, with `--name <worker>`,
  since Wrangler does not read `cloudflare.config.ts`. Note that in the
  README or AGENTS.md.
- Whether `cf migrate` removed the Wrangler file or left it, make sure only
  one config is authoritative, and say which.

## 5. Prove parity

For each mode, compare against the inventory and the baseline:

| Mode | Worker name | Bindings | Routes/crons/consumers | Compat date | Result |

Every binding must be present with the same binding name and the same
resource; every trigger the same. Then `npx cf workers types`, typecheck,
tests, `npx cf dev` with a `curl` of the main routes, `npx cf build` and
`npx cf deploy --dry-run --mode <mode>` for each mode. Anything missing or
different is ❌ — fix it or list it as a blocker.

## 6. Preview and pull request

`npx cf previews deploy` and smoke-test it. Open a pull request:

```
Migrate <worker> from Wrangler to cf (cloudflare.config.ts)

<the parity table>

**Changed by hand:** <list, or nothing>
**Still Wrangler:** secrets (`wrangler secret put --name <worker>`), logs (`wrangler tail <worker>`)
**Preview:** <url>
**Checks:** types ✅ · tests ✅ · dry run ✅ per mode
**Production:** not deployed. After merge, ask me to ship it.
```

## Output

```
<Migrated | Blocked>: <worker> — <n> bindings, <n> triggers, <n> modes
PR: <link> · Preview: <url>
Manual fixes: <list or none> · Blockers: <list or none>
```
