# Production deploy checklist

Each item is ✅, ⚠️ (proceed, but say so on the card) or ❌ (blocks).

- **Commit** — the deploy is from the default branch's head after merge, or
  the commit the owner named, and the working tree is clean (❌).
- **Checks** — typecheck, tests and `cf deploy --dry-run --mode
  $CF_PRODUCTION_MODE` pass on that commit (❌).
- **Preview** — a preview of the same code answered the touched routes (❌
  if it failed; ⚠️ if there is none because the change is config-only).
- **Resources** — every production resource the config binds exists or is
  listed to be created; nothing will be deleted or renamed (❌ for a
  delete or rename the owner has not named).
- **Data** — D1 migrations are listed with what each does; a destructive
  one (drop, rename, rewrite) has a backup or export first (❌ without one).
- **Secrets** — every `bindings.secret()` exists on the production Worker;
  check the list, not the values (❌ if missing).
- **Routes and triggers** — new or changed routes, crons, queue consumers
  and email addresses are listed (⚠️).
- **Compatibility** — `compatibilityDate` or compatibility flags changed
  (⚠️, say what moves).
- **Rollback** — the version now live is recorded so it can be restored (❌
  if you could not read it).
