#!/usr/bin/env python3
"""Build every template's plugin/apps/<name>/{app.yaml,app.html}.

Each app is one spec below. app.yaml and app.html are both written from it, so
the actions a page offers are always the actions its app.yaml declares, and
the page is scripts/apps/page.html around the shared view in lib.js and the
MCP Apps host protocol copied verbatim from Claybot's package-creator
template (scripts/apps/protocol.js). The spec's `card` is the section the
owning skill gains, between the <!-- card --> markers, so a rebuild rewrites
it rather than adding a second.

    python3 scripts/apps/build.py          # write everything
    python3 scripts/apps/build.py --check  # fail if anything is out of date
"""

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))

# ---- schema pieces ---------------------------------------------------------

S = lambda d=None, **kw: dict({"type": "string"}, **({"description": d} if d else {}), **kw)
I = lambda d=None: dict({"type": "integer"}, **({"description": d} if d else {}))
B = lambda d=None: dict({"type": "boolean"}, **({"description": d} if d else {}))
A = lambda items, d=None: dict({"type": "array", "items": items}, **({"description": d} if d else {}))


def O(props, required=(), d=None):
    o = {"type": "object"}
    if d:
        o["description"] = d
    if required:
        o["required"] = list(required)
    o["properties"] = props
    return o


FINDING = O({
    "id": S("Stable id, echoed back in values.keep."),
    "title": S("One line naming the problem."),
    "severity": S("critical, high, medium or low."),
    "category": S(),
    "confidence": I("0-100, from the rubric."),
    "file": S("Path in the repository."),
    "line": I("Line in the new file."),
    "url": S("Link to the line on the forge."),
    "body": S("Why it is a problem and what to do, in Markdown."),
    "suggestion": S("Replacement code, when there is one."),
    "hunk": S("The unified diff hunk around the line, copied from git diff, @@ header included."),
}, ["id", "title"])

FILE = O({
    "path": S(),
    "patch": S("Unified diff of this file, @@ headers included."),
    "url": S(),
    "status": S("added, modified, removed or renamed."),
}, ["path", "patch"])

DOC = O({
    "path": S("Path of the document in the repository or workspace."),
    "reason": S("One line: what the change made wrong here."),
    "before": S("The document's Markdown before your edit; omit for a new file."),
    "after": S("The document's Markdown with your edit, in full."),
    "url": S(),
    "status": S("added or changed."),
}, ["path", "after"])

LINK = O({"title": S(), "url": S()}, ["url"])

REF = S("Anything you need to pick this up later (repository, issue URL, run id). It comes back with the decision.")

# Where each fallback sentence starts: a card is refused on a chat platform
# turn and missing when the deployment has package apps off.
OFFERED = ("When `{tool}` is among your tools and this turn did not come from Slack, "
           "Telegram or Discord")
FALLBACK = ("If `{tool}` is not among your tools, is refused, or comes back expired or "
            "cancelled, carry on exactly as the steps above say — the card is an extra, "
            "never a reason to stop.")
COMMENTS = ("`values.comments`, when present, is a JSON array of `{{target, quote?, body}}`: "
            "the owner's own comments. {targets}")
PICKED = "`values.{field}` is a JSON array of the ids the owner {verb}."


def review_card(tool, step, extra_input, post_rule):
    return f"""{OFFERED.format(tool=tool)}, let your owner see the review before it is posted: after {step}, and before you write the final message:

1. Call `{tool}` with the pull request's `title`, `url`, `repo`, `number`, `author`, your `summary`, every finding you kept (`id`, `title`, `severity`, `category`, `file`, `line`, `body`, and `hunk`: the diff hunk around the line, copied from `git diff`){extra_input}, and `files`: the changed files' patches (`path`, `patch`), at most 20.
2. It waits for the owner (up to 15 minutes) and returns the decision:
   - `post` — write the comment from the findings whose ids are in `values.keep` (a JSON array), with `values.summary` in place of your summary when present. {post_rule}
   - `request_changes` — the same, with the first line **Changes requested**.
   - `hold` — post nothing: end the turn with an empty final message.

   {COMMENTS.format(targets="A target is `path:line`, `path:-line` for a removed line, or `finding <id>`. Add each under a **Reviewer notes** heading, quoting the target, in the owner's words.")}
3. {FALLBACK.format(tool=tool)}"""


APPS = []


def app(**kw):
    APPS.append(kw)


# ---- Development -----------------------------------------------------------

REVIEW_ACTIONS = [
    {"id": "post", "label": "Post review", "tone": "primary"},
    {"id": "request_changes", "label": "Post as changes requested", "tone": "danger"},
    {"id": "hold", "label": "Don't post", "tone": "neutral"},
]


def review_sections(extra=()):
    return [
        {"type": "header", "link": "url", "meta": ["repo", "number", "author"], "chips": ["verdict"]},
        {"type": "edit", "key": "summary", "field": "summary", "label": "Summary", "rows": 4,
         "hint": "Edit it to change what the comment opens with."},
        *extra,
        {"type": "checks", "key": "checks", "label": "Checks"},
        {"type": "findings", "key": "findings", "field": "keep", "label": "Findings", "noun": "kept",
         "empty": "No finding met the bar. Post says so."},
        {"type": "diffs", "key": "files", "label": "Files changed"},
    ]


def review_input(extra_props=None, finding=FINDING):
    props = {
        "title": S("The pull request's title."),
        "url": S("The pull request's URL."),
        "repo": S("owner/name."),
        "number": I(),
        "author": S(),
        "summary": S("Your two or three sentence summary of the change, Markdown."),
        "verdict": S("Your one-word read: clean, minor or blocking."),
        "checks": A(O({"name": S(), "status": S("pass, fail or pending."), "url": S()}, ["name"]), "CI checks."),
        "findings": A(finding, "Every finding you kept after scoring."),
        "files": A(FILE, "The changed files, at most 20."),
    }
    props.update(extra_props or {})
    return O(props, ["title", "url", "findings"])


app(
    template="pr-reviewer", skill="review-pr", name="pr-review", title="Pull request review",
    description="Use before posting a pull request review: shows the owner the findings with their diff hunks and every changed file, lets them drop findings, comment on lines and edit the summary, and returns whether to post.",
    mode="gate", comments=True, input=review_input(), actions=REVIEW_ACTIONS,
    sections=review_sections(),
    card=review_card("app_pr_review", "step 7's second check", "",
                     "Keep the format in `references/comment-format.md`."),
)

app(
    template="deploy-config-reviewer", skill="review-deploy-change", name="deploy-review",
    title="Deployment change review",
    description="Use before posting a review of a deployment change (Dockerfile, Kubernetes, Helm, Terraform, CI): shows the owner each risk by category with its diff hunk and the changed files, and returns whether to post.",
    mode="gate", comments=True,
    input=review_input({"kinds": A(S(), "What the change touches: docker, kubernetes, helm, terraform, ci.")}),
    actions=REVIEW_ACTIONS,
    sections=[{**review_sections()[0], "chips": ["verdict", "kinds"]}] + review_sections()[1:],
    card=review_card("app_deploy_review", "step 3", ", with `category` one of security, reliability or cost, and `kinds`",
                     "Group them by category as step 4 says."),
)

app(
    template="migration-checker", skill="check-migration", name="migration-review",
    title="Migration review",
    description="Use before posting a migration review: shows the owner each locking, downtime, data-loss or rollback risk beside its SQL and the migration diffs, with the engine assumed, and returns whether to post.",
    mode="gate", comments=True,
    input=review_input({
        "engine": S("The database engine and version the advice assumes."),
        "sql": S("The SQL the migrations run, from step 2, one statement per line."),
    }),
    actions=REVIEW_ACTIONS,
    sections=review_sections([
        {"type": "kv", "label": "Assumes", "keys": [["engine", "Engine"]]},
        {"type": "text", "key": "sql", "label": "SQL it runs"},
    ]),
    card=review_card("app_migration_review", "step 4",
                     ", with `category` one of lock, downtime, data-loss or rollback, plus `engine` and the `sql` from step 2",
                     "Keep the format step 5 gives."),
)

app(
    template="docs-keeper", skill="update-docs", name="docs-review", title="Docs review",
    description="Use before opening a documentation pull request: shows the owner each document you changed, rendered with the new passages marked and what was taken out, lets them comment on any passage and drop files, and returns whether to open the pull request.",
    mode="gate", comments=True,
    input=O({
        "title": S("The merged pull request's title."),
        "url": S("The merged pull request's URL."),
        "repo": S(),
        "number": I(),
        "summary": S("What changed in behaviour, and so in the docs, Markdown."),
        "docs": A(DOC, "Every document you changed."),
    }, ["title", "docs"]),
    actions=[
        {"id": "open_pr", "label": "Open the docs PR", "tone": "primary"},
        {"id": "revise", "label": "Revise first", "tone": "neutral", "note": "optional"},
        {"id": "skip", "label": "Leave the docs", "tone": "neutral", "note": "optional"},
    ],
    sections=[
        {"type": "header", "link": "url", "meta": ["repo", "number"]},
        {"type": "markdown", "key": "summary", "label": "What changed"},
        {"type": "docs", "key": "docs", "field": "files", "label": "Documents", "noun": "included"},
    ],
    card=f"""{OFFERED.format(tool="app_docs_review")}, show your owner the edits before step 5 publishes them:

1. Call `app_docs_review` with the merged pull request's `title`, `url`, `repo`, `number`, a `summary` of what changed, and `docs`: each file you edited with its `path`, a one-line `reason`, the whole file `before` (omit for a new file) and `after` your edit.
2. It waits for the owner (up to 15 minutes) and returns the decision. {PICKED.format(field="files", verb="kept in")} {COMMENTS.format(targets="A target is `path:L<line>`, the line the commented passage starts on in `after`; `quote` is the text they selected.")}
   - `open_pr` — apply every comment, drop the files not in `values.files`, then publish as step 5 says.
   - `revise` — apply the comments and the note, then call `app_docs_review` again with the new text. Stop after three rounds and publish what the owner last saw, with their open comments listed in the pull request body.
   - `skip` — discard the branch and reply with one line saying the owner kept the docs as they are, plus the note if there is one.
3. {FALLBACK.format(tool="app_docs_review")}""",
)

app(
    template="test-writer", skill="write-tests", name="test-results", title="Tests to add",
    description="Use before opening a pull request with new tests: shows the owner the run's result, each test and what it covers, and the test files' diffs, lets them drop tests and comment on lines, and returns whether to open the pull request.",
    mode="gate", comments=True,
    input=O({
        "title": S("The pull request the tests are for."),
        "url": S(),
        "repo": S(),
        "number": I(),
        "run": O({"command": S(), "passed": I(), "failed": I(), "skipped": I(), "output": S("The last 80 lines of output.")}),
        "tests": A(O({"id": S("The test's name."), "file": S(), "covers": S("The behaviour it proves, one line."), "status": S("pass or fail.")}, ["id"])),
        "files": A(FILE, "The test files' diffs."),
    }, ["title", "tests"]),
    actions=[
        {"id": "open_pr", "label": "Open the tests PR", "tone": "primary"},
        {"id": "revise", "label": "Change first", "tone": "neutral", "note": "optional"},
        {"id": "discard", "label": "Discard", "tone": "neutral", "note": "optional"},
    ],
    sections=[
        {"type": "header", "link": "url", "meta": ["repo", "number"]},
        {"type": "kv", "key": "run", "label": "Run", "keys": [["command", "Command"], ["passed", "Passed"], ["failed", "Failed"], ["skipped", "Skipped"]]},
        {"type": "text", "key": "run.output", "label": "Output"},
        {"type": "items", "key": "tests", "field": "keep", "label": "Tests", "title": "id", "chips": ["status"], "meta": ["file", "covers"], "noun": "kept", "checked": True, "comment": True, "target": "test"},
        {"type": "diffs", "key": "files", "label": "Test files"},
    ],
    card=f"""{OFFERED.format(tool="app_test_results")}, show your owner the tests after step 5 proves them and before step 6 publishes:

1. Call `app_test_results` with the pull request's `title`, `url`, `repo`, `number`, the `run` (`command`, `passed`, `failed`, `skipped`, last lines of `output`), each test (`id` = its name, `file`, `covers`, `status`) and `files`: the diffs of the test files.
2. It waits for the owner (up to 15 minutes) and returns the decision. {PICKED.format(field="keep", verb="kept")} {COMMENTS.format(targets="A target is `path:line` in a test file or `test <name>`.")}
   - `open_pr` — remove the tests not in `values.keep`, apply the comments, run again, and publish as step 6 says.
   - `revise` — apply the comments and the note, prove the tests again, and call `app_test_results` again. Stop after three rounds and publish what the owner last saw.
   - `discard` — delete the branch and reply with one line saying the owner declined the tests, plus the note.
3. {FALLBACK.format(tool="app_test_results")}""",
)

app(
    template="issue-triager", skill="triage-issue", name="issue-triage", title="Issue triage",
    description="Use before posting a triage comment on a new issue: shows the owner its type, severity, suggested labels, possible duplicates and what is missing, lets them pick labels, mark a duplicate and edit the reply, and returns whether to post.",
    mode="gate", comments=False,
    input=O({
        "title": S("The issue's title."),
        "url": S(),
        "repo": S(),
        "number": I(),
        "type": S("bug, feature, question, docs or chore."),
        "severity": S("critical, high, medium or low; bugs only."),
        "labels": A(O({"id": S("The label's exact name."), "why": S()}, ["id"]), "Labels you suggest."),
        "duplicates": A(O({"id": S("Issue number."), "title": S(), "url": S(), "why": S("Why it looks the same.")}, ["id"])),
        "missing": A(O({"id": S(), "title": S("What is missing, as the question to the reporter.")}, ["title"])),
        "reply": S("The comment you would post, Markdown."),
    }, ["title", "reply"]),
    actions=[
        {"id": "post", "label": "Post reply", "tone": "primary"},
        {"id": "duplicate", "label": "Post as duplicate", "tone": "neutral", "needs": "duplicates"},
        {"id": "hold", "label": "Don't post", "tone": "neutral"},
    ],
    sections=[
        {"type": "header", "link": "url", "meta": ["repo", "number"], "chips": ["type", "severity"]},
        {"type": "items", "key": "labels", "field": "labels", "label": "Labels", "title": "id", "meta": ["why"], "noun": "chosen", "checked": True},
        {"type": "items", "key": "duplicates", "field": "duplicates", "label": "Possible duplicates", "title": "title", "meta": ["id", "why"], "noun": "marked"},
        {"type": "items", "key": "missing", "label": "Missing from the report"},
        {"type": "edit", "key": "reply", "field": "reply", "label": "Reply", "rows": 8},
    ],
    card=f"""{OFFERED.format(tool="app_issue_triage")}, let your owner check the triage before step 7's comment is posted:

1. Call `app_issue_triage` with the issue's `title`, `url`, `repo`, `number`, `type`, `severity`, your suggested `labels` (`id` = exact label name, `why`), `duplicates` (`id` = issue number, `title`, `url`, `why`), `missing` (each question to the reporter as `title`) and the `reply` you wrote.
2. It waits for the owner (up to 15 minutes) and returns the decision. {PICKED.format(field="labels", verb="kept")} `values.duplicates` is the same for duplicates, and `values.reply`, when present, is the owner's edit of your reply — post it as written.
   - `post` — post the reply (theirs if edited). Apply `values.labels` when TRIAGE_APPLY_LABELS is "true", otherwise name them as suggestions.
   - `duplicate` — post a short, warm comment pointing at the issues in `values.duplicates`, and suggest the `duplicate` label. Never close it.
   - `hold` — post nothing: end the turn with an empty final message.
3. {FALLBACK.format(tool="app_issue_triage")}""",
)

# ---- Monitoring --------------------------------------------------------------

app(
    template="alert-triager", skill="triage-alert", name="alert-triage", title="Alert triage",
    description="Use after writing an alert's triage note, in the console only: shows the owner the rating, the recent changes it may tie to and the checks to run, without waiting, so they can ask you to dig deeper or mark a false alarm later.",
    mode="show", comments=True, ref=True,
    input=O({
        "title": S("The alert, one line."),
        "severity": S("sev1, sev2 or sev3, from step 3."),
        "source": S("pagerduty, datadog or grafana."),
        "url": S("The alert in its tool."),
        "summary": S("Your note from step 5, Markdown."),
        "changes": A(O({"id": S(), "title": S(), "url": S(), "when": S(), "why": S("Why it could be the cause.")}, ["title"]), "Recent changes that could explain it."),
        "next": A(O({"name": S("A check or step for a person."), "detail": S(), "url": S()}, ["name"])),
        "ref": REF,
    }, ["title", "summary"]),
    actions=[
        {"id": "dig", "label": "Dig deeper", "tone": "primary", "note": "optional"},
        {"id": "false_alarm", "label": "False alarm", "tone": "neutral", "note": "required"},
        {"id": "escalate", "label": "Draft an escalation", "tone": "neutral", "note": "optional"},
    ],
    sections=[
        {"type": "header", "link": "url", "chips": ["severity", "source"]},
        {"type": "markdown", "key": "summary", "label": "Triage", "comment": True},
        {"type": "items", "key": "changes", "label": "Changes that could explain it", "meta": ["when", "why"], "comment": True, "target": "change"},
        {"type": "checks", "key": "next", "label": "Check first"},
    ],
    card=f"""{OFFERED.format(tool="app_alert_triage")}, after step 5 also call `app_alert_triage` with the alert's `title`, `severity`, `source`, `url`, your note as `summary`, the candidate `changes` from step 4 (`title`, `url`, `when`, `why`), the checks for a person as `next`, and a `ref` naming the alert and the repositories you looked at. It returns at once — never wait on it; your note is still the reply.

The owner may decide later; that arrives as a new turn carrying the decision and `values.ref`. {COMMENTS.format(targets="A target is `summary:L<line>` or `change <id>`.")}
- `dig` — investigate further along the note and comments, and reply with what you found.
- `false_alarm` — record the alert's signature and the note in `alerts/false-alarms.md`, which step 2 reads when it dedupes.
- `escalate` — draft a short escalation message for a person to send: impact, what is known, what is not.

{FALLBACK.format(tool="app_alert_triage")}""",
)

app(
    template="error-investigator", skill="investigate-error", name="error-fix", title="Error investigation",
    description="Use after writing an error's investigation note, in the console only: shows the owner the cause, the stack frames, the change that introduced it and the proposed patch, without waiting, so they can ask for a draft pull request later.",
    mode="show", comments=True, ref=True,
    input=O({
        "title": S("The error, one line."),
        "url": S("The Sentry issue."),
        "release": S(),
        "culprit": S("file:line where it is thrown."),
        "cause": S("The root cause from step 3, Markdown."),
        "frames": A(O({"name": S("function (file:line)"), "detail": S("The line of code."), "url": S()}, ["name"]), "The in-app frames, innermost first."),
        "suspect": A(O({"title": S(), "url": S(), "author": S(), "when": S()}, ["title"]), "The change from step 4."),
        "files": A(FILE, "The proposed fix as a diff."),
        "ref": REF,
    }, ["title", "cause"]),
    actions=[
        {"id": "open_draft_pr", "label": "Open a draft PR", "tone": "primary", "note": "optional"},
        {"id": "dig", "label": "Dig deeper", "tone": "neutral", "note": "optional"},
        {"id": "not_a_bug", "label": "Not a bug", "tone": "neutral", "note": "required"},
    ],
    sections=[
        {"type": "header", "link": "url", "meta": ["release", "culprit"]},
        {"type": "markdown", "key": "cause", "label": "Cause", "comment": True},
        {"type": "checks", "key": "frames", "label": "Stack"},
        {"type": "items", "key": "suspect", "label": "Introduced by", "meta": ["author", "when"]},
        {"type": "diffs", "key": "files", "label": "Proposed fix"},
    ],
    card=f"""{OFFERED.format(tool="app_error_fix")}, after step 6 also call `app_error_fix` with the error's `title`, `url`, `release`, `culprit`, your `cause`, the in-app `frames`, the `suspect` change, the proposed fix as `files` (a diff per file), and a `ref` naming the repository, the release and the Sentry issue. It returns at once — never wait on it; your note is still the reply.

The owner may decide later; that arrives as a new turn carrying the decision and `values.ref`. {COMMENTS.format(targets="A target is `cause:L<line>` or `path:line` in the fix.")}
- `open_draft_pr` — open a draft pull request with the fix, the comments applied. The owner's click is the permission ERROR_OPEN_DRAFT_PR otherwise gives; never push to a default branch or merge.
- `dig` — look further along the note and comments, and reply with what changed in your understanding.
- `not_a_bug` — record the issue and the note in `errors/not-bugs.md` and read it before investigating the same error again.

{FALLBACK.format(tool="app_error_fix")}""",
)

app(
    template="uptime-watcher", skill="check-uptime", name="uptime-status", title="Uptime",
    description="Use after a check that found a change, in the console only: shows every URL's status, latency and what changed, without waiting, so the owner can re-check or mute URLs later.",
    mode="show", comments=False, ref=True,
    input=O({
        "title": S("One line: what changed."),
        "checks": A(O({"id": S("The URL."), "status": S("up, down, slow or recovered."), "ms": I("Latency."), "code": I("HTTP status."), "change": S("What changed since the last check."), "since": S()}, ["id", "status"])),
        "ref": REF,
    }, ["title", "checks"]),
    actions=[
        {"id": "recheck", "label": "Check again", "tone": "primary"},
        {"id": "mute", "label": "Mute selected", "tone": "neutral", "note": "required", "needs": "urls"},
    ],
    sections=[
        {"type": "header"},
        {"type": "items", "key": "checks", "field": "urls", "label": "URLs", "title": "id", "url": "id", "chips": ["status"], "meta": ["code", "ms", "change", "since"], "labels": {"ms": "ms", "code": "HTTP", "since": "since"}, "noun": "selected"},
    ],
    card=f"""{OFFERED.format(tool="app_uptime_status")}, when step 3 reports a change, also call `app_uptime_status` with a one-line `title` and every URL in `checks` (`id` = the URL, `status`, `ms`, `code`, `change`, `since`). It returns at once — never wait on it, and never call it for an all-clear.

The owner may decide later; that arrives as a new turn. {PICKED.format(field="urls", verb="selected")}
- `recheck` — run step 1 now and report.
- `mute` — add each selected URL with the note (it says for how long) to `uptime/muted.md`, and skip them in step 3's report until then.

{FALLBACK.format(tool="app_uptime_status")}""",
)

app(
    template="incident-scribe", skill="write-postmortem", name="postmortem", title="Postmortem",
    description="Use before saving an incident's postmortem, in the console only: shows the owner the draft rendered beside the timeline, lets them comment on any passage, and returns whether to file it or revise.",
    mode="gate", comments=True,
    input=O({
        "title": S("The incident."),
        "doc": S("The postmortem draft, Markdown."),
        "timeline": A(O({"at": S("HH:MM"), "who": S(), "what": S()}, ["what"])),
    }, ["title", "doc"]),
    actions=[
        {"id": "file", "label": "File it", "tone": "primary"},
        {"id": "revise", "label": "Revise", "tone": "neutral", "note": "optional"},
    ],
    sections=[
        {"type": "header"},
        {"type": "markdown", "key": "doc", "label": "Draft", "comment": True, "path": "postmortem.md"},
        {"type": "timeline", "key": "timeline", "label": "Timeline"},
    ],
    card=f"""{OFFERED.format(tool="app_postmortem")}, before step 5 saves it, call `app_postmortem` with the incident as `title`, the draft as `doc` and the timeline entries (`at`, `who`, `what`). It waits for the owner (up to 15 minutes). {COMMENTS.format(targets="A target is `postmortem.md:L<line>`; `quote` is the text they selected.")}
- `file` — apply the comments and save as step 5 says.
- `revise` — apply the comments and the note, keeping every fact to the timeline, and call `app_postmortem` again. Stop after three rounds and save what the owner last saw.

{FALLBACK.format(tool="app_postmortem")}""",
)

# ---- Productivity --------------------------------------------------------------

app(
    template="chat-helper", skill="research-and-report", name="report", title="Report",
    description="Use when a request in the console needed real work and the answer is longer than a chat reply: shows the owner the report rendered with its sources, without waiting, so they can comment on passages and ask for a follow-up.",
    mode="show", comments=True, ref=True,
    input=O({
        "title": S("The question, one line."),
        "report": S("The report, Markdown."),
        "sources": A(LINK, "What you read."),
        "ref": REF,
    }, ["title", "report"]),
    actions=[
        {"id": "follow_up", "label": "Follow up", "tone": "primary", "note": "optional"},
    ],
    sections=[
        {"type": "header"},
        {"type": "markdown", "key": "report", "label": "Report", "comment": True},
        {"type": "items", "key": "sources", "label": "Sources"},
    ],
    card=f"""{OFFERED.format(tool="app_report")} and the result runs past what step 5 fits in a reply, also call `app_report` with the question as `title`, the full `report` and its `sources`, and a `ref` naming where your notes are. Keep your reply to the short answer. It returns at once — never wait on it.

The owner may follow up later; that arrives as a new turn with the note. {COMMENTS.format(targets="A target is `report:L<line>`; `quote` is the text they selected.")} Answer each comment, then the note.

{FALLBACK.format(tool="app_report")}""",
)

app(
    template="meeting-notes", skill="summarize-meeting", name="meeting-summary", title="Meeting summary",
    description="Use before filing a meeting summary, in the console only: shows the owner the decisions, action items with owners and dates, and open questions, lets them comment on any line, and returns whether to file it.",
    mode="gate", comments=True,
    input=O({
        "title": S("The meeting."),
        "date": S("YYYY-MM-DD."),
        "people": A(S()),
        "decisions": A(O({"id": S(), "title": S("The decision.")}, ["title"])),
        "actions": A(O({"id": S(), "title": S("The task."), "owner": S("Only as said; empty when nobody was named."), "due": S()}, ["title"])),
        "questions": A(O({"id": S(), "title": S()}, ["title"])),
    }, ["title"]),
    actions=[
        {"id": "file", "label": "File it", "tone": "primary"},
        {"id": "revise", "label": "Fix first", "tone": "neutral", "note": "optional"},
    ],
    sections=[
        {"type": "header", "meta": ["date"]},
        {"type": "items", "key": "decisions", "label": "Decisions", "comment": True, "target": "decision"},
        {"type": "items", "key": "actions", "label": "Action items", "meta": ["owner", "due"], "labels": {"due": "due"}, "comment": True, "target": "action"},
        {"type": "items", "key": "questions", "label": "Open questions", "comment": True, "target": "question"},
    ],
    card=f"""{OFFERED.format(tool="app_meeting_summary")}, before step 4 files it, call `app_meeting_summary` with the meeting `title`, `date`, `people`, and the `decisions`, `actions` (`title`, `owner`, `due`) and open `questions`, each with an `id`. It waits for the owner (up to 15 minutes). {COMMENTS.format(targets="A target is `decision <id>`, `action <id>` or `question <id>`.")}
- `file` — apply the comments (an owner or a date they give is now stated) and file as step 4 says.
- `revise` — apply the comments and the note and call `app_meeting_summary` again. Stop after three rounds and file what the owner last saw.

{FALLBACK.format(tool="app_meeting_summary")}""",
)

app(
    template="research-assistant", skill="research-brief", name="research-brief", title="Research brief",
    description="Use after writing a research brief, in the console only: shows the owner the brief, each claim with its confidence and sources, without waiting, so they can comment and pick claims to dig into.",
    mode="show", comments=True, ref=True,
    input=O({
        "title": S("The question."),
        "brief": S("The brief from step 5, Markdown."),
        "claims": A(O({"id": S(), "title": S("The claim."), "confidence": S("high, medium or low."), "sources": A(LINK)}, ["id", "title"])),
        "ref": REF,
    }, ["title", "brief"]),
    actions=[
        {"id": "dig", "label": "Dig into selected", "tone": "primary", "note": "optional", "needs": "claims"},
        {"id": "follow_up", "label": "Ask a follow-up", "tone": "neutral", "note": "required"},
    ],
    sections=[
        {"type": "header"},
        {"type": "markdown", "key": "brief", "label": "Brief", "comment": True},
        {"type": "items", "key": "claims", "field": "claims", "label": "Claims", "chips": ["confidence"], "links": "sources", "noun": "selected", "comment": True, "target": "claim"},
    ],
    card=f"""{OFFERED.format(tool="app_research_brief")}, after step 5 also call `app_research_brief` with the question as `title`, the `brief`, each claim (`id`, `title`, `confidence`, `sources`) and a `ref` naming your notes file. It returns at once — never wait on it; the brief is still your reply.

The owner may decide later; that arrives as a new turn. {PICKED.format(field="claims", verb="selected")} {COMMENTS.format(targets="A target is `brief:L<line>` or `claim <id>`.")}
- `dig` — research the selected claims deeper, with the note as the angle, and reply with what held and what did not.
- `follow_up` — treat the note as a new question on the same notes.

{FALLBACK.format(tool="app_research_brief")}""",
)

app(
    template="writing-editor", skill="edit-draft", name="edit-review", title="Edits",
    description="Use when returning an edited draft in the console: shows the owner each change beside the original with why, and the whole revision, lets them reject changes and comment on passages, and returns whether to use it.",
    mode="gate", comments=True,
    input=O({
        "title": S("What the draft is."),
        "changes": A(O({"id": S(), "before": S("The original wording."), "after": S("Your wording."), "why": S("One line.")}, ["id"])),
        "revision": S("The whole revised draft with every change applied, Markdown."),
    }, ["title", "changes", "revision"]),
    actions=[
        {"id": "accept", "label": "Use these edits", "tone": "primary"},
        {"id": "revise", "label": "Revise", "tone": "neutral", "note": "optional"},
    ],
    sections=[
        {"type": "header"},
        {"type": "changes", "key": "changes", "field": "accepted", "label": "Changes", "noun": "accepted"},
        {"type": "markdown", "key": "revision", "label": "Revision", "comment": True, "path": "draft"},
    ],
    card=f"""{OFFERED.format(tool="app_edit_review")}, at step 5 call `app_edit_review` with what the draft is as `title`, each important change (`id`, `before`, `after`, `why`) and the whole `revision`. It waits for the owner (up to 15 minutes). {PICKED.format(field="accepted", verb="accepted")} {COMMENTS.format(targets="A target is `draft:L<line>`; `quote` is the text they selected.")}
- `accept` — reply with the final text: your revision with the unaccepted changes put back to the original, and the comments applied. Note any preference they stated in STYLE.md.
- `revise` — apply the comments and the note and call `app_edit_review` again. Stop after three rounds and reply with what the owner last saw.

{FALLBACK.format(tool="app_edit_review")}""",
)

# ---- Deployment ------------------------------------------------------------------

app(
    template="release-notes", skill="draft-release-notes", name="notes-review", title="Release notes",
    description="Use when a release-notes draft is written, in the console only: shows the owner the notes rendered with the version you suggest, lets them comment on any line, and returns whether to open the CHANGELOG pull request, revise, or keep the draft.",
    mode="gate", comments=True,
    input=O({
        "title": S("<version> — <date>."),
        "repo": S(),
        "range": S("The tag range, like v1.4.0...main."),
        "notes": S("The notes as step 5 writes them, Markdown."),
    }, ["title", "notes"]),
    actions=[
        {"id": "changelog_pr", "label": "Open CHANGELOG PR", "tone": "primary"},
        {"id": "revise", "label": "Revise", "tone": "neutral", "note": "optional"},
        {"id": "keep", "label": "Keep the draft", "tone": "neutral"},
    ],
    sections=[
        {"type": "header", "meta": ["repo", "range"]},
        {"type": "markdown", "key": "notes", "label": "Notes", "comment": True, "path": "notes"},
    ],
    card=f"""{OFFERED.format(tool="app_notes_review")}, after step 5 call `app_notes_review` with `<version> — <date>` as `title`, `repo`, `range` and the `notes`. It waits for the owner (up to 15 minutes). {COMMENTS.format(targets="A target is `notes:L<line>`; `quote` is the text they selected.")}
- `changelog_pr` — apply the comments and open a pull request that adds the notes to CHANGELOG.md; reply with its link.
- `revise` — apply the comments and the note and call `app_notes_review` again. Stop after three rounds.
- `keep` — reply with the notes, comments applied, as the draft.

{FALLBACK.format(tool="app_notes_review")}""",
)

app(
    template="release-manager", skill="cut-release", name="release-scope", title="Release scope",
    description="Use at step 2, before proposing the version: shows the owner what the release would carry (each merged change with its risk and the readiness checks), lets them flag changes that must not ship, and returns whether to go on to the release card or stop.",
    mode="gate", comments=True,
    input=O({
        "title": S("<repository> <last tag>...<commit>."),
        "repo": S(),
        "base": S("The last tag."),
        "head": S("The commit to release."),
        "changes": A(O({"id": S("PR number or short sha."), "title": S(), "url": S(), "author": S(), "kind": S("breaking, feature, fix or chore."), "risk": S("high, medium or low.")}, ["id", "title"])),
        "checks": A(O({"name": S(), "status": S("pass, fail or pending."), "url": S(), "detail": S()}, ["name"]), "Readiness checks from step 2."),
    }, ["title", "changes"]),
    actions=[
        {"id": "continue", "label": "Go on to sign-off", "tone": "primary"},
        {"id": "stop", "label": "Don't release", "tone": "danger", "note": "optional"},
    ],
    sections=[
        {"type": "header", "meta": ["repo", "base", "head"]},
        {"type": "checks", "key": "checks", "label": "Readiness"},
        {"type": "items", "key": "changes", "field": "blockers", "label": "Changes", "chips": ["kind", "risk"], "meta": ["id", "author"], "noun": "flagged as blockers", "hint": "Tick a change that must not ship in this release.", "comment": True, "target": "change"},
    ],
    card=f"""{OFFERED.format(tool="app_release_scope")}, after step 2 and before step 3, call `app_release_scope` with `title`, `repo`, `base` (the last tag), `head` (the commit), every change since the tag (`id`, `title`, `url`, `author`, `kind`, `risk`) and the readiness `checks`. It waits for the owner (up to 15 minutes). `values.blockers` is a JSON array of the change ids the owner says must not ship. {COMMENTS.format(targets="A target is `change <id>`.")}
- `continue` with no blockers — go on to step 3, taking the comments into the notes.
- `continue` with blockers — a tag cannot leave a change out: say which blockers sit before `head`, propose the last commit before the first one as the release point, and stop until someone agrees.
- `stop` — stop, and reply with the note.

The sign-off in step 4 is still Claybot's release card. {FALLBACK.format(tool="app_release_scope")}""",
)

app(
    template="cloudflare-sdlc-expert", skill="ship-on-cloudflare", name="production-deploy", title="Production deploy",
    description="Use at step 7.3, as the sign-off before a production deploy: shows the owner the worker, commit and preview, the checklist, each resource and data change with its risk, what ships, and the config diff, lets them hold back resource changes, and returns whether to deploy, keep it on preview, or stop.",
    mode="gate", comments=True,
    input=O({
        "title": S("<worker> → <mode>."),
        "repo": S(),
        "commit": S("The short sha being deployed."),
        "mode": S("The --mode the config is evaluated with."),
        "preview_url": S("The preview deployment of the same code."),
        "checks": A(O({"name": S(), "status": S("pass, fail, warn or pending."), "url": S(), "detail": S()}, ["name"]), "The deploy checklist, one row per item."),
        "notes": S("What ships, for users, and the rollback plan with the version now live, Markdown."),
        "resources": A(O({
            "id": S("Stable id, echoed back in values.hold."),
            "title": S("The binding and resource, e.g. DATABASE → example-production-database."),
            "kind": S("d1, kv, r2, queue, vectorize, route, cron, secret, migration or other."),
            "action": S("added, changed or removed."),
            "risk": S("high, medium or low."),
            "detail": S("One line: what happens when it is applied."),
        }, ["id", "title"]), "Every production resource, route, trigger and D1 migration the deploy creates or changes."),
        "files": A(FILE, "The diff of cloudflare.config.ts and migrations since the version now live, at most 10."),
    }, ["title", "commit", "checks"]),
    actions=[
        {"id": "deploy", "label": "Deploy to production", "tone": "primary"},
        {"id": "keep_preview", "label": "Keep it on preview", "tone": "neutral", "note": "optional"},
        {"id": "stop", "label": "Don't deploy", "tone": "danger", "note": "optional"},
    ],
    sections=[
        {"type": "header", "link": "preview_url", "meta": ["repo", "commit", "mode"]},
        {"type": "checks", "key": "checks", "label": "Checklist"},
        {"type": "markdown", "key": "notes", "label": "What ships", "comment": True, "path": "notes"},
        {"type": "items", "key": "resources", "field": "hold", "label": "Resource changes", "chips": ["action", "risk"], "meta": ["kind"], "body": "detail", "noun": "held back", "hint": "Tick a change that must not be applied in this deploy.", "comment": True, "target": "resource", "empty": "No resource, route or data changes."},
        {"type": "diffs", "key": "files", "label": "Config changes"},
    ],
    card=f"""{OFFERED.format(tool="app_production_deploy")}, this card is the sign-off in step 7.3: call `app_production_deploy` with `<worker> → <mode>` as `title`, `repo`, `commit`, `mode`, the `preview_url`, the checklist as `checks` (✅ pass, ⚠️ warn, ❌ fail, with the detail), `notes` (what ships and the rollback plan), every production `resources` change (`id`, `title`, `kind`, `action`, `risk`, `detail`) and the `files` diff of the config and migrations. Never call it with a ❌ in the checklist. It waits for the owner (up to 15 minutes). `values.hold` is a JSON array of the resource ids the owner says must not be applied. {COMMENTS.format(targets="A target is `notes:L<line>`, `path:line` in a diff, or `resource <id>`.")}
- `deploy` with nothing held — that is the sign-off for this worker, mode and commit: go on to step 7.4. Apply the comments only if they need no code change; otherwise stop and say what they ask.
- `deploy` with changes held — a deploy cannot leave a resource change out: stop, say which held changes the code depends on, and propose the change without them back on the branch (steps 3 to 6).
- `keep_preview` — do not deploy; reply with the preview URL, the note and the comments.
- `stop` — do not deploy; reply with the note.

A sign-off is good for that commit only: if the commit moves before you deploy, call the card again. {FALLBACK.format(tool="app_production_deploy")} Without the card the sign-off is still required, in words as step 7.3 says.""",
)

# ---- Automation ------------------------------------------------------------------

app(
    template="dependency-watch", skill="check-dependencies", name="dependency-report", title="Dependency report",
    description="Use after updating the dependency report, in the console only: shows the owner each finding ranked by risk with its fix version and advisory, without waiting, so they can accept a risk or ask for a re-check later.",
    mode="show", comments=True, ref=True,
    input=O({
        "title": S("<repository>: one line on what changed since the last check."),
        "url": S("The Dependency report issue."),
        "deps": A(O({"id": S("<ecosystem>:<package>"), "title": S("package current -> fixed"), "risk": S("critical, high, medium or low."), "kind": S("vulnerable, major or minor."), "advisory": S(), "url": S(), "reachable": S("yes, no or unknown.")}, ["id", "title"])),
        "ref": REF,
    }, ["title", "deps"]),
    actions=[
        {"id": "accept_risk", "label": "Accept risk for selected", "tone": "danger", "note": "required", "needs": "deps"},
        {"id": "recheck", "label": "Check again now", "tone": "neutral"},
    ],
    sections=[
        {"type": "header", "link": "url"},
        {"type": "items", "key": "deps", "field": "deps", "label": "Dependencies", "chips": ["risk", "kind"], "meta": ["advisory", "reachable"], "labels": {"reachable": "reachable:"}, "noun": "selected", "comment": True, "target": "dep"},
    ],
    card=f"""{OFFERED.format(tool="app_dependency_report")}, after step 4 also call `app_dependency_report` with a one-line `title`, the report issue's `url`, the findings as `deps` (`id` = `<ecosystem>:<package>`, `title`, `risk`, `kind`, `advisory`, `url`, `reachable`) and a `ref` naming the repository. It returns at once — never wait on it.

The owner may decide later; that arrives as a new turn with `values.ref`. {PICKED.format(field="deps", verb="selected")} {COMMENTS.format(targets="A target is `dep <id>`.")}
- `accept_risk` — list the selected findings with the note under **Accepted risks** in the report issue, and leave them out of later rankings until a new advisory appears.
- `recheck` — run the check now, even off schedule.

{FALLBACK.format(tool="app_dependency_report")}""",
)

app(
    template="stale-sweeper", skill="sweep-stale", name="stale-sweep", title="Stale items",
    description="Use after a sweep, in the console only: lists the items that stayed silent after a nudge, without waiting, so the owner can pick which to close or keep open.",
    mode="show", comments=False, ref=True,
    input=O({
        "title": S("<repository>: n items ready to close."),
        "items": A(O({"id": S("Issue or PR number."), "title": S(), "url": S(), "kind": S("issue or pr."), "quiet": S("How long it has been quiet."), "nudged": S("When you nudged it.")}, ["id", "title"])),
        "ref": REF,
    }, ["title", "items"]),
    actions=[
        {"id": "close", "label": "Close selected", "tone": "danger", "note": "optional", "needs": "items"},
        {"id": "keep_open", "label": "Keep selected open", "tone": "neutral", "needs": "items"},
    ],
    sections=[
        {"type": "header"},
        {"type": "items", "key": "items", "field": "items", "label": "Silent after a nudge", "chips": ["kind"], "meta": ["id", "quiet", "nudged"], "labels": {"quiet": "quiet", "nudged": "nudged"}, "noun": "selected"},
    ],
    card=f"""{OFFERED.format(tool="app_stale_sweep")}, when step 3 finds items that stayed silent, also call `app_stale_sweep` with a one-line `title`, those `items` (`id`, `title`, `url`, `kind`, `quiet`, `nudged`) and a `ref` naming the repository. It returns at once — never wait on it.

The owner may decide later; that arrives as a new turn with `values.ref`. {PICKED.format(field="items", verb="selected")}
- `close` — close each selected item with a kind closing comment (the note, if any, goes in it). The owner's selection is the permission STALE_CLOSE otherwise gives, for these items only; `pinned`, `security` and `keep-open` items are still never touched.
- `keep_open` — add the `keep-open` label to each selected item if you can, otherwise list them in `stale/keep-open.md`, and never nudge them again.

{FALLBACK.format(tool="app_stale_sweep")}""",
)

app(
    template="repo-digest", skill="write-digest", name="digest", title="Repo digest",
    description="Use after writing the digest, in the console only: lists what merged, grouped, with risks flagged, without waiting, so the owner can pick changes for you to look at more closely.",
    mode="show", comments=False, ref=True,
    input=O({
        "title": S("<repository> since <last digest>."),
        "changes": A(O({"id": S("PR number or short sha."), "title": S(), "url": S(), "author": S(), "group": S("The heading it sits under."), "risk": S("Set only when it carries one: high, medium or low.")}, ["id", "title"])),
        "ref": REF,
    }, ["title", "changes"]),
    actions=[
        {"id": "look", "label": "Look closer at selected", "tone": "primary", "note": "optional", "needs": "changes"},
    ],
    sections=[
        {"type": "header"},
        {"type": "items", "key": "changes", "field": "changes", "label": "Merged", "chips": ["group", "risk"], "meta": ["id", "author"], "noun": "selected"},
    ],
    card=f"""{OFFERED.format(tool="app_digest")}, after step 4 also call `app_digest` with `title`, every change in the digest (`id`, `title`, `url`, `author`, `group`, `risk` when it has one) and a `ref` naming the repository and range. It returns at once — never wait on it; the digest is still your reply.

The owner may decide later; that arrives as a new turn. {PICKED.format(field="changes", verb="selected")}
- `look` — read each selected change's diff and discussion and reply with what it does, what it risks and what to watch, with the note as the angle.

{FALLBACK.format(tool="app_digest")}""",
)

app(
    template="weekly-report", skill="write-weekly-report", name="weekly-report", title="Weekly report",
    description="Use after writing the weekly report, in the console only: shows what shipped, what is stuck and what needs a decision, without waiting, so the owner can pick items to discuss.",
    mode="show", comments=True, ref=True,
    input=O({
        "title": S("Week of <date>."),
        "summary": S("The report's opening, Markdown."),
        "shipped": A(O({"id": S(), "title": S(), "url": S(), "repo": S()}, ["title"])),
        "stuck": A(O({"id": S(), "title": S(), "url": S(), "repo": S(), "why": S()}, ["id", "title"])),
        "decisions": A(O({"id": S(), "title": S(), "url": S()}, ["id", "title"])),
        "ref": REF,
    }, ["title"]),
    actions=[
        {"id": "discuss", "label": "Discuss selected", "tone": "primary", "note": "optional", "needs": "stuck"},
    ],
    sections=[
        {"type": "header"},
        {"type": "markdown", "key": "summary", "label": "Summary", "comment": True},
        {"type": "items", "key": "decisions", "label": "Needs a decision", "comment": True, "target": "decision"},
        {"type": "items", "key": "stuck", "field": "stuck", "label": "Stuck", "meta": ["repo", "why"], "noun": "selected", "comment": True, "target": "stuck"},
        {"type": "items", "key": "shipped", "label": "Shipped", "meta": ["repo"]},
    ],
    card=f"""{OFFERED.format(tool="app_weekly_report")}, after step 4 also call `app_weekly_report` with `title`, the opening as `summary`, and the `shipped`, `stuck` (with `why`) and `decisions` items, each with an `id`, plus a `ref` naming the week. It returns at once — never wait on it; the report is still your reply.

The owner may decide later; that arrives as a new turn. {PICKED.format(field="stuck", verb="selected")} {COMMENTS.format(targets="A target is `summary:L<line>`, `decision <id>` or `stuck <id>`.")}
- `discuss` — for each selected stuck item, dig into why it is stuck (reviews, CI, discussion) and reply with what would unstick it, answering each comment.

{FALLBACK.format(tool="app_weekly_report")}""",
)

# ---- writing -----------------------------------------------------------------------


def fields(spec):
    props = {}
    if spec.get("comments"):
        props["comments"] = {"type": "string", "title": "Comments",
                             "description": "JSON array of {target, quote, body}: the owner's comments.",
                             "maxLength": 20000}
    for sec in spec["sections"]:
        f = sec.get("field")
        if not f:
            continue
        if sec["type"] == "edit":
            props[f] = {"type": "string", "title": sec["label"], "description": "The owner's edit; absent when unchanged.", "maxLength": 20000}
        else:
            props[f] = {"type": "string", "title": sec["label"], "description": "JSON array of the ids the owner " + sec.get("noun", "selected") + ".", "maxLength": 8000}
    if spec.get("ref"):
        props["ref"] = {"type": "string", "title": "Reference", "description": "The ref the call passed, echoed back.", "maxLength": 2000}
    return O(props) if props else None


def yaml_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9 _.,/()'-]*", s) and s.lower() not in ("yes", "no", "true", "false", "null", "on", "off") and ": " not in s:
        return s
    return json.dumps(s, ensure_ascii=False)


def yaml(v, indent=0):
    pad = "  " * indent
    out = []
    if isinstance(v, dict):
        for k, x in v.items():
            if isinstance(x, (dict, list)) and x:
                if isinstance(x, list) and all(not isinstance(i, (dict, list)) for i in x):
                    out.append(f"{pad}{k}: [{', '.join(yaml_scalar(i) for i in x)}]")
                else:
                    out.append(f"{pad}{k}:")
                    out.append(yaml(x, indent + 1))
            else:
                out.append(f"{pad}{k}: {yaml_scalar(x) if not isinstance(x, (dict, list)) else ('{}' if isinstance(x, dict) else '[]')}")
    elif isinstance(v, list):
        for x in v:
            if isinstance(x, dict) and all(not isinstance(i, (dict, list)) for i in x.values()):
                out.append(f"{pad}- {{ {', '.join(f'{k}: {yaml_scalar(i)}' for k, i in x.items())} }}")
            elif isinstance(x, dict):
                inner = yaml(x, indent + 1).splitlines()
                out.append(f"{pad}- " + inner[0].lstrip())
                out.extend(inner[1:])
            else:
                out.append(f"{pad}- {yaml_scalar(x)}")
    return "\n".join(out)


def app_yaml(spec):
    doc = {"title": spec["title"], "description": spec["description"], "mode": spec["mode"], "input": spec["input"]}
    doc["actions"] = [{k: v for k, v in a.items() if k != "needs"} for a in spec["actions"]]
    f = fields(spec)
    if f:
        doc["fields"] = f
    head = (f"# plugin/apps/{spec['name']}/app.yaml — the tool app_{spec['name'].replace('-', '_')}.\n"
            "# Generated by scripts/apps/build.py; change the spec there and rebuild.\n"
            "# No csp: the page reaches nothing outside itself.\n\n")
    return head + yaml(doc) + "\n"


def squeeze(text):
    """Drop comment-only lines and indentation: the pages ship twenty times
    over in one catalog clone, and the readable source is lib.js."""
    out = []
    for line in text.splitlines():
        t = line.strip()
        if not t or t.startswith("//") or (t.startswith("/*") and t.endswith("*/")):
            continue
        out.append(t)
    return "\n".join(out)


def app_html(spec, page, protocol, lib):
    lib = squeeze(lib)
    head, css_rest = page.split("<style>", 1)
    css, rest = css_rest.split("</style>", 1)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    page = head + "<style>\n" + squeeze(css) + "\n</style>" + rest
    view = {
        "title": spec["title"],
        "comments": bool(spec.get("comments")),
        "ref": bool(spec.get("ref")),
        "actions": spec["actions"],
        "sections": [{k: v for k, v in s.items() if k != "checked"} | ({"checked": True} if s.get("checked") else {}) for s in spec["sections"]],
    }
    js = json.dumps(view, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (page.replace("{{NAME}}", spec["name"]).replace("{{TITLE}}", spec["title"])
            .replace("{{PROTOCOL}}", protocol.rstrip()).replace("{{LIB}}", lib.rstrip()).replace("{{APP}}", js))


CARD_START, CARD_END = "<!-- card -->", "<!-- /card -->"


def skill_with_card(text, spec):
    body = f"{CARD_START}\n## Card\n\n{spec['card'].strip()}\n{CARD_END}\n"
    if CARD_START in text:
        return re.sub(re.escape(CARD_START) + r".*?" + re.escape(CARD_END) + r"\n?", lambda m: body, text, flags=re.S)
    return text.rstrip("\n") + "\n\n" + body


def main():
    check = "--check" in sys.argv
    read = lambda p: open(p, encoding="utf-8").read()
    page, protocol, lib = read(os.path.join(HERE, "page.html")), read(os.path.join(HERE, "protocol.js")), read(os.path.join(HERE, "lib.js"))
    stale = []

    def put(path, content):
        old = read(path) if os.path.exists(path) else None
        if old == content:
            return
        stale.append(os.path.relpath(path, ROOT))
        if not check:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w", encoding="utf-8").write(content)

    templates = sorted(d for d in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, d, "template.yaml")))
    covered = {s["template"] for s in APPS}
    missing = [t for t in templates if t not in covered]
    for spec in APPS:
        # The view's rules, checked here so a bad spec fails the build rather than a card.
        ids = [a["id"] for a in spec["actions"]]
        assert 1 <= len(ids) <= 10 and len(set(ids)) == len(ids), spec["name"]
        fields_ = {s.get("field") for s in spec["sections"]}
        for a in spec["actions"]:
            assert a.get("needs") in (None, *fields_), (spec["name"], a)
        for s in spec["sections"]:
            assert s["type"] in ("header", "markdown", "docs", "findings", "diffs", "items", "changes", "checks", "timeline", "kv", "text", "edit"), (spec["name"], s)
        base = os.path.join(ROOT, spec["template"], "plugin")
        put(os.path.join(base, "apps", spec["name"], "app.yaml"), app_yaml(spec))
        put(os.path.join(base, "apps", spec["name"], "app.html"), app_html(spec, page, protocol, lib))
        sk = os.path.join(base, "skills", spec["skill"], "SKILL.md")
        put(sk, skill_with_card(read(sk), spec))
    if missing:
        print("templates without an app:", ", ".join(missing))
    if check and stale:
        print("out of date; run python3 scripts/apps/build.py:\n  " + "\n  ".join(stale))
        sys.exit(1)
    if not check:
        print(f"{len(APPS)} apps; wrote {len(stale)} files")


if __name__ == "__main__":
    main()
