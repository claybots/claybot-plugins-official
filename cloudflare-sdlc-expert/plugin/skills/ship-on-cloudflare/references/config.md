# cloudflare.config.ts

TypeScript configuration for the whole of Cloudflare, starting with Workers.
cf evaluates only its default export, once per `--mode`. Prefer it over
Wrangler config for new projects; the LSP autocompletes every binding.

## A Worker

```ts
import { bindings, defineConfig } from "cf/config";
import * as entrypoint from "./src/index.js" with { type: "cf-worker" };

export default defineConfig(({ mode }) => ({
  worker: {
    name: "example-worker",
    entrypoint,
    compatibilityDate: "2026-09-27",
    env: {
      ENVIRONMENT: bindings.text(`This is ${mode}`),
    },
  },
}));
```

## Bindings

Name every resource per mode, so a preview never touches production data.

```ts
env: {
  API_URL: bindings.text(mode === "production" ? "https://example.com" : "https://staging.example.com"),
  API_TOKEN: bindings.secret(),                       // value set by the owner, never here
  CACHE: bindings.kv({ id: mode === "production" ? "<production-namespace-id>" : "<staging-namespace-id>" }),
  DATABASE: bindings.d1({ name: `example-${mode}-database` }),
  UPLOADS: bindings.r2({ name: `example-${mode}-uploads` }),
  JOBS: bindings.queue<{ userId: string }>({ name: `example-${mode}-jobs` }),
  AI: bindings.ai(),
  SEARCH_INDEX: bindings.vectorize({ name: `example-${mode}-search` }),
  API: bindings.worker({ worker: `example-${mode}-api` }),       // service binding
},
```

A typed queue binding types both the producer's `send` and the consumer's
batch. After changing bindings, run `npx cf workers types`.

## Triggers

```ts
import { defineConfig, triggers } from "cf/config";

worker: {
  triggers: [
    triggers.fetch({ pattern: "example.com/*" }),
    triggers.scheduled({ schedule: "0 * * * *" }),
    triggers.queue({ name: "jobs", maxBatchSize: 10 }),
    triggers.email({ addresses: ["support@example.com"] }),
  ],
},
```

A `fetch` pattern on a zone routes production traffic: it counts as a
production change in the deploy checklist.

## Rules

- No secret values, account tokens or `.dev.vars` contents in the file.
- Keep `compatibilityDate` unless the change needs a newer runtime; moving it
  is a behaviour change to call out.
- Durable Objects, Workflows and Containers: check the generated config
  against the docs (cloudflare-docs MCP) — `cf migrate` leaves them for
  manual review.
