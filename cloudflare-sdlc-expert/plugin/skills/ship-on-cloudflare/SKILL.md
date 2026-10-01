---
name: ship-on-cloudflare
description: Plan, build, test, preview and deploy a Cloudflare Workers project with the cf CLI — new projects (cf init), features and bindings in cloudflare.config.ts, pull request checks with a preview deploy, and production deploys after sign-off. Use for any request to build on, check, or deploy to Cloudflare, and for every pull request on a Cloudflare project.
---

# Ship on Cloudflare

`references/cf-cli.md` is how cf behaves (auth, output, flags, the commands
known to exist); `references/config.md` is `cloudflare.config.ts`;
`references/deploy-checklist.md` is the production bar. Run cf as `npx cf`
when the project lists `cf` in its devDependencies, otherwise `npx --yes cf`.

## 0. Orient

1. Work out which path this turn is:
   - **Pull request** — the turn starts with `GitHub pull request …` (or
     `… comment` for a comment). A comment that does not address you, and a
     pull request from a bot or still a draft, gets an empty final message.
     Otherwise do steps 1, 4 and 5 on the pull request's head and reply in
     the **Pull request comment** format below.
   - **Request** — someone asked for a change or a deploy: all steps, and
     step 7 only when they asked to ship to production.
2. In the repository (or the subdirectory named), find the project:
   - `cloudflare.config.ts` → a cf project.
   - `wrangler.toml`, `wrangler.json` or `wrangler.jsonc` and no
     `cloudflare.config.ts` → a Wrangler project. Use Wrangler's commands for
     it, and say once that the migrate-to-cf skill can move it. Do not
     migrate unasked.
   - Neither, and the request is to start one → `npx --yes cf init <dir>
     --package-manager npm` (`cf init .` inside an existing app detects its
     framework and configures it). Then go on from step 3.
   - Neither, and nothing to start → reply that this repository has no
     Cloudflare project, and stop.
3. Read the repository's `AGENTS.md`/`CLAUDE.md`, `package.json` scripts and
   the config. Note the Workers, their bindings, triggers and modes.
4. `npx cf whoami`. A 401 or no account → stop and say
   `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` need linking; do not try
   `cf auth login` (it needs a browser).

## 1. Plan

Restate the change in two or three lines: the code it touches, every binding
or resource it adds or changes (with the mode each belongs to), triggers,
and anything only the owner can provide (a secret's value, a domain). When
the change adds a production resource or a route, or touches more than a
handful of files, post the plan and wait for a go-ahead before step 2.

## 2. Branch

Branch `cf/<short-slug>` from the default branch's head. Never commit to the
default branch.

## 3. Build

1. Write the code. Keep Workers runtime APIs (`fetch`, `env.<BINDING>`,
   `ctx.waitUntil`) — no Node-only modules unless the config enables Node
   compatibility.
2. Declare bindings and triggers in `cloudflare.config.ts` with the
   `bindings` and `triggers` helpers, naming resources per mode
   (`example-${mode}-…`), as `references/config.md` shows. Regenerate types
   with `npx cf workers types`.
3. A resource that must exist before deploy (a D1 database, a KV namespace, an
   R2 bucket, a queue): find the command with `npx cf cli search "<task>"`,
   read `npx cf schema <resource> <op>`, run it with `--dry-run`, then for
   real — for non-production modes only. Production resources wait for
   step 7.
4. D1 schema changes are migration files under the project's migrations
   directory, never ad-hoc SQL against a remote database.
5. A new Worker secret: declare it with `bindings.secret()` and tell the owner
   the exact command to set it (`npx wrangler secret put <NAME> --name
   <worker>`, since cf cannot set a single secret yet). Never ask for the
   value in chat and never set it yourself.

## 4. Verify

Run, in order, stopping at the first failure to fix it (or, on a pull
request, to report it):

1. Install (`npm ci`, or the lockfile's package manager).
2. Typecheck (`npx cf workers types`, then the project's typecheck script or
   `npx tsc --noEmit`).
3. Tests (the project's test script; Workers tests usually run in
   `@cloudflare/vitest-pool-workers`).
4. `npx cf dev` in the background, then `curl` each route you touched on
   `http://localhost:5173/` (the port it prints); stop it afterwards.
5. `npx cf build`, then `npx cf deploy --prebuilt --mode "$CF_PRODUCTION_MODE"
   --dry-run`, which validates the production build without credentials or
   uploads.

A Wrangler project uses `npx wrangler dev`, `npx wrangler deploy --dry-run`
and `npx wrangler types` in place of 2, 4 and 5.

## 5. Preview

`npx cf previews deploy` (Wrangler: `npx wrangler versions upload`) and take
the preview URL from its JSON. `curl` the routes you touched on it. A preview
binds the non-production resources; say so when a behaviour depends on data.

## 6. Pull request

Push the branch and open a pull request:

```
<what changed, one paragraph>

**Cloudflare:** <worker(s)> · bindings added/changed: <list or none> · triggers: <list or none>
**Preview:** <url>
**Checks:** typecheck ✅ · tests ✅ (<n>) · dry run ✅ · preview smoke ✅
**Owner to do:** <secrets to set, domains, or "nothing">
**Production:** not deployed. Ask me to ship it after merge.
```

## 7. Production

Only when someone asked to ship to production.

1. Use the default branch's head after the pull request merged (or the
   commit they named). Re-run step 4 on it.
2. Work through `references/deploy-checklist.md`. Any ❌ stops here: reply
   with the blockers.
3. Get sign-off for this worker, mode and commit. In the console, the
   production deploy card below; on a chat platform, post the checklist, the
   resource changes and the preview URL and wait for "yes, deploy <worker>
   to production". Anything else — silence, "looks good?", a thumbs-up — is
   not a sign-off.
4. Create any production resources from step 3 (dry run first), apply D1
   migrations to the production database through the project's migration
   command (find it with `cf cli search "apply d1 migrations"`), then
   `npx cf deploy --mode "$CF_PRODUCTION_MODE"`.
5. Smoke-test the production routes you touched. If one fails, roll back to
   the previous version at once (`npx cf cli search "roll back worker
   deployment"`; Wrangler: `npx wrangler rollback --name <worker>`) and
   report.

## Output

**Request:**

```
<Done | Blocked | Needs you>: <one line>
Branch/PR: <link> · Preview: <url>
Checks: <the step 4 results>
Production: <not deployed | deployed <worker> <version> at <time>, smoke ✅ | rolled back: <why>>
You: <what the owner still has to do, or nothing>
```

**Pull request comment** (empty final message when the pull request does not
touch a Cloudflare project):

```
**Cloudflare check** · <worker(s)> · <short sha>

Typecheck <✅|❌> · Tests <✅|❌ n failed> · Dry run <✅|❌> · Preview <url|❌>

<each failure: the command, the first relevant error lines in a code block, and the likely fix>
<bindings or triggers this PR adds or changes, and resources that must exist before production>
```

<!-- card -->
## Card

When `app_production_deploy` is among your tools and this turn did not come from Slack, Telegram or Discord, this card is the sign-off in step 7.3: call `app_production_deploy` with `<worker> → <mode>` as `title`, `repo`, `commit`, `mode`, the `preview_url`, the checklist as `checks` (✅ pass, ⚠️ warn, ❌ fail, with the detail), `notes` (what ships and the rollback plan), every production `resources` change (`id`, `title`, `kind`, `action`, `risk`, `detail`) and the `files` diff of the config and migrations. Never call it with a ❌ in the checklist. It waits for the owner (up to 15 minutes). `values.hold` is a JSON array of the resource ids the owner says must not be applied. `values.comments`, when present, is a JSON array of `{target, quote?, body}`: the owner's own comments. A target is `notes:L<line>`, `path:line` in a diff, or `resource <id>`.
- `deploy` with nothing held — that is the sign-off for this worker, mode and commit: go on to step 7.4. Apply the comments only if they need no code change; otherwise stop and say what they ask.
- `deploy` with changes held — a deploy cannot leave a resource change out: stop, say which held changes the code depends on, and propose the change without them back on the branch (steps 3 to 6).
- `keep_preview` — do not deploy; reply with the preview URL, the note and the comments.
- `stop` — do not deploy; reply with the note.

A sign-off is good for that commit only: if the commit moves before you deploy, call the card again. If `app_production_deploy` is not among your tools, is refused, or comes back expired or cancelled, carry on exactly as the steps above say — the card is an extra, never a reason to stop. Without the card the sign-off is still required, in words as step 7.3 says.
<!-- /card -->
