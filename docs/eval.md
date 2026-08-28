# RCA accuracy: methodology, measured numbers, and limitations

This project makes two distinct claims about correctness, and they are
verified very differently:

1. The **deterministic rule-based fallback** (`services/investigation-service/app/services/fallback.py`)
   is regression-tested against a golden dataset in CI on every push.
2. The **LLM RCA synthesis path** (`rca_synthesizer` in `app/agents/investigators.py`)
   was measured against the same golden dataset by hand, against a live local
   model. It is *not* run in CI (see "Why the LLM eval isn't in CI" below).

Neither of these is a substitute for validation against real historical
incidents at whatever infrastructure this is eventually pointed at. Both are
regression harnesses, not proof of real-world accuracy.

## 1. Rule-based fallback: 100% on 11 golden cases (CI-gated)

`eval/run_eval.py` and `eval/golden_cases.py` (in `services/investigation-service/`)
encode 11 synthetic incidents: one per rule in the fallback engine (OOM,
crashloop, error storm, latency, CPU, memory, dependency timeout, deployment
regression), a no-signal "insufficient evidence" case, and two **off-vocabulary
adversarial cases** (see below). `tests/test_eval_golden.py` runs this as part
of the normal pytest suite, so it's gated in CI (`.github/workflows/ci.yml`)
on every push — a regression in the rule table fails the build.

This mostly proves the rule table matches its own test cases; it says
relatively little about how often those 8 hardcoded patterns actually match a
real, unforeseen incident. They're keyed to fairly specific keyword matches
(see `fallback.py`) and were written against this project's own sample-app
fault-injection vocabulary.

### A real false-positive bug the adversarial cases caught

Two cases were added specifically to test the opposite failure mode from
everything else in this doc: does the rule engine correctly say "Insufficient
evidence" for an incident type none of the 8 rules were written for, or does
it false-positive-match an unrelated rule because a keyword check is broader
than intended? A DNS resolution failure and a TLS certificate expiry case
(neither containing any of the rules' match keywords, by inspection) were
added on the assumption they'd both cleanly return "Insufficient evidence".

They didn't. Both were misdiagnosed as **"Downstream dependency timeouts"**
at 84% confidence. The cause: the `dependency_timeout` rule matched on
`"timeout" in text_blob`, but the log-summary evidence item's
auto-generated text is always `f"errors={n} warnings={n} timeouts={n}
oomkilled={n}"` — the literal substring `"timeouts="` is present **whenever
timeout_count is 0 just as much as when it's 50**. The rule fired on almost
any incident with a log-summary item at all, regardless of whether timeouts
actually occurred. Fixed by checking the real `timeout_count > 0` instead of
matching on the rendered summary string; the `dependency_timeout_cascade`
case (which has a genuine timeout_count of 5) still passes after the fix, and
both adversarial cases now correctly return "Insufficient evidence".

This is the kind of bug golden cases built only from "here's what each rule
*should* match" can never catch — it took a case deliberately designed to
match *none* of the rules to surface it.

## 2. LLM synthesis path: measured 0% → 100% (manually, not CI-gated)

`eval/run_llm_eval.py` runs the same golden dataset through the *actual*
`rca_synthesizer` + `citation_validator` production code, against a live
model-gateway + Ollama. This is where the real story is.

### What we found running it for the first time

Against the golden set, with a live Ollama instance genuinely reachable and
responding (not a mock, not a stub):

| Model | Fallback rate | Root-cause accuracy |
|---|---|---|
| `llama3.2:1b` | 0% (LLM ran every time) | **0%** |
| `llama3.2` (3b) | 0% (LLM ran every time) | **0%** |

Every single case, on both model sizes, came back `root_cause: "Insufficient
evidence"` — including the textbook error-storm case where the evidence
contained a log line reading `"error_storm injected failure"` verbatim and a
`HighErrorRate` alert. Manually calling the model outside the harness
confirmed this wasn't a fluke: the model correctly identified and cited the
right evidence IDs, but still labeled the verdict "Insufficient evidence."

Both model sizes failing identically is a strong signal this was a **prompt
bug, not a capability limit**. Two contributing causes were found and fixed:

1. **The system prompt offered "Insufficient evidence" as an explicit escape
   hatch** ("If evidence is insufficient, set root_cause to 'Insufficient
   evidence'"), and the evidence was rendered as a raw Python dict repr
   rather than readable text. Small local models took the safe/lazy answer
   on nearly every case rather than committing to a diagnosis. Fix: render
   evidence as plain `- id: summary` lines, ask a direct question ("what is
   the most likely root cause"), and frame "Insufficient evidence" as a last
   resort rather than a default option.
2. **A `k8s-unavailable` evidence item** (present whenever the context
   collector can't reach a Kubernetes API, which is normal for this Compose
   demo) was phrased as `"Kubernetes unavailable: <reason>"` — worded just
   like a plausible root cause. After fix (1), 4 of 8 cases converged on the
   model citing *this* evidence item as the cause instead of the actual
   metric/log evidence. Fix: reworded to `"Kubernetes evidence unavailable
   for this investigation (collector could not reach the cluster: ...).
   This is a monitoring gap, not a root cause -- do not cite it as the cause
   of the incident."` (`app/services/evidence.py`).

After both fixes, re-running the identical harness against the identical
model (`llama3.2`, 3b) scored:

| | Before | After |
|---|---|---|
| Root-cause accuracy (8 non-trivial golden cases) | 0% | **100%** |
| Fallback rate | 0% | 0% |
| Per-call latency | 15-40s (isolated) | 15-40s (isolated) |

The 1B model was re-tested with the same fixed prompt and, while it stopped
defaulting to "Insufficient evidence," it began corrupting the JSON structure
instead (nesting `root_cause` as an object rather than a string) — it is not
reliable at this task's multi-field structured-output demands regardless of
prompt wording. **Use the 3B model (`OLLAMA_MODEL=llama3.2` in `.env`), not
the 1B variant**, unless you have a strong reason to trade accuracy for
speed.

### A real, separate infra bug found along the way

While chasing this, the *full 5-LLM-call pipeline* (4 optional investigator
enrichments + 1 synthesis call) was found to fall back to the rule engine on
CPU-only hardware even after the prompt fix — not because of a bad answer,
but because of **timeout and circuit-breaker misconfiguration**:

- `docker-compose.yml` hardcoded `REQUEST_TIMEOUT_SECONDS: "60"` for
  model-gateway with no env-var override at all, and defaulted
  `OLLAMA_TIMEOUT_SECONDS`/`LLM_TIMEOUT_SECONDS` to 60s if `.env` didn't set
  them — silently overriding any code-level default. Fixed to
  `${OLLAMA_TIMEOUT_SECONDS:-180}` throughout, and `.env`/`.env.example` now
  set it explicitly.
- `libs/common/resilience.py`'s `with_retry()` called the circuit breaker's
  `record_failure()` once per retry *attempt* rather than once per outer
  call. With `retries=3`, a single call that times out three times in a row
  burned 3 of a `failure_threshold=5` in one shot — meaning two merely-slow
  (not broken) calls could trip the breaker and silently force fallback for
  the rest of the investigation. Fixed to record one failure per exhausted
  call, matching what retries are supposed to buy you.

Both are covered by their own justification comments at the call sites; the
circuit-breaker fix is also unit-tested (`libs/common/tests/test_resilience.py`).

## 3. Why the LLM eval isn't in CI

`run_llm_eval.py` requires a real, reachable model-gateway with an actual
model loaded and responding — it is not mocked. That means:

- It's slow (minutes per run: 8 cases × 15-40s+ each).
- It's non-deterministic (LLM sampling varies run to run, even at low
  temperature).
- It depends on infrastructure GitHub Actions runners don't have (a
  multi-gigabyte local model, or a paid hosted API key).

Running it is a manual step, documented here so the numbers above are
reproducible rather than asserted:

```bash
cd services/investigation-service
MODEL_GATEWAY_URL=http://localhost:8040 LLM_MODEL=llama3.2 LLM_TIMEOUT_SECONDS=180 \
  PYTHONPATH=../..:. .venv/bin/python -m eval.run_llm_eval --json-out eval/llm-report.json
```

(Requires the full Compose stack up, with `ollama pull llama3.2` already run.)

## 4. What these numbers do NOT tell you

- **This is not a real-world accuracy measurement.** 11 golden cases, all
  synthetic. The 8 non-trivial ones are still designed around this project's
  own sample-app fault vocabulary; the 2 adversarial cases prove the rule
  engine doesn't false-positive on totally unrelated incident types, but
  that's a much narrower claim than "handles unfamiliar infrastructure." A
  100% score here means the prompt fix works on the cases we wrote and the
  rule engine doesn't false-fire on two specific off-vocabulary probes — not
  that the system will correctly diagnose an arbitrary unfamiliar incident.
- **No historical-incident validation exists.** There is no golden set built
  from real past incidents with known, agreed-upon root causes. Before
  pointing this at real infrastructure, build one from your own postmortems
  and re-run this harness against it.
- **No LLM-as-judge or human-rating loop exists** for cases where the
  "correct" answer isn't a simple keyword match. The current scoring is
  keyword-in-string matching (see `golden_cases.py`), which is precise but
  brittle — a correct paraphrase can score as a false negative unless its
  synonyms are added to the case (this happened once already; see the
  `crashloop_backoff` case's comment in `golden_cases.py`).
- **Latency is real and matters.** Even fixed, a full LLM-backed
  investigation on CPU-only local hardware takes 90-250+ seconds. That's
  workable for an assistive/human-approves-everything tool; it is not
  "real-time."

## 5. Beyond eval: real remediation execution, and case-based learning

Two capabilities beyond RCA accuracy were added and verified live (not just
unit-tested) against the running local stack.

### Real remediation execution (not a stub)

`RESTART_SERVICE` proposals now execute a genuine `docker restart` against
the real `sample-app` container via the Docker Engine API
(`services/remediation-service/app/services/docker_executor.py`), gated by
two independent, code-enforced checks on top of the existing human-approval
requirement:

1. `ALLOW_COMPOSE_RESTART` (existing config flag).
2. A hard allowlist (`RESTART_ALLOWED_SERVICES`) enforced in code — verified
   live that a direct attempt to restart `postgres` is correctly refused,
   even though nothing about the Docker API itself would stop it.

Bug found in the process: the RCA→proposal mapper only ever creates a
`RESTART_SERVICE` proposal if the literal word "restart" appears in the
RCA's root cause or next-steps text, and none of the 8 rule-based RCA
outputs said "restart" — the feature was unreachable through the normal
incident flow. Fixed by adding a restart step to the CrashLoopBackOff rule
(`fallback.py`), the one scenario where it's a genuinely sensible
suggestion, and confirmed the mapper now produces the proposal correctly.

`ROLLBACK` and `SCALE` remain honest stubs (`"Mutation stub recorded"`).

### Case-based learning (not model fine-tuning)

`POST /investigations/{id}/feedback` (investigation-service) lets an
operator mark an RCA `correct` / `incorrect` / `partial`. A `correct`
verdict does more than log the verdict: the RCA and the evidence that
grounded it are pushed into knowledge-service as a new document
(`app/services/feedback.py`), so a future, similar incident's
`runbook_investigator` can retrieve and cite it via the existing RAG path —
verified live: the learned document search-ranked *above* the seed runbooks
(score 0.61 vs. 0.48) for a semantically similar query, and resubmitting
feedback on the same investigation correctly reused the existing
`learned_doc_id` instead of creating a duplicate.

This is deliberately not fine-tuning. Fine-tuning needs a meaningful volume
of labeled examples before it's worth the infrastructure; retrieval-based
learning gets useful on the very first confirmed incident, degrades
gracefully, and is fully inspectable (you can read every "lesson" the system
has learned as a plain document in the knowledge base). It's the
appropriate scale of "learning" for a project at this incident volume — see
the roadmap discussion in the project README for when fine-tuning would
become the right next step.

### Durable event dispatch (Redis Streams, not Kafka)

Incident creation used to trigger context collection via a fire-and-forget
HTTP call inside a FastAPI `BackgroundTask` (`incident-service`'s
`trigger_context_collection`): if that single request failed for any reason
— context-service mid-restart, a network blip — the event was gone, logged
as a warning, nothing ever retried it.

`incident-service` now publishes an `incident.created` event to a Redis
Stream (`libs/common/eventbus.py`) instead, and `context-service` runs a
background consumer (`app/services/eventbus_consumer.py`) reading it via a
named consumer group. This buys the two things a bus is actually for here:
the event survives the consumer being briefly down (it waits in the stream,
not lost), and a transient failure during processing leaves the entry
unacked for redelivery rather than dropping it — a permanent failure
(incident not found upstream) is acked so it isn't retried forever. The old
HTTP path is kept as an explicit fallback: if the bus itself is unreachable,
`publish()` returns `None` and the direct call fires instead, so a Redis
outage degrades to the old behavior rather than losing events outright.

**Why Redis Streams and not Kafka**, since both were on the table: at this
project's real message volume — a handful of incidents at a time on a
single host — a Kafka broker (plus ZooKeeper/KRaft) is a lot of operational
weight for no throughput this system will ever need. Redis is already
running here for caching, so this was marginal cost, not new infrastructure,
and Streams' consumer groups already give durability and redelivery. The
bus's publish/consume surface is deliberately narrow (3 methods) so a
Kafka-backed implementation could be dropped in behind the same interface
later if real throughput ever justified it, without touching caller code —
matching this project's stubbed `ROLLBACK`/`SCALE` actions is not enough;
this is a real, working default, with a real off-ramp if it stops being the
right one.

**Verified live**, not just unit-tested: triggered a real `error_storm`
fault, confirmed the real Alertmanager alert fired and reached
incident-service, confirmed the event landed in the real Redis stream
(`XRANGE` showed the actual `incident_id`), confirmed the consumer group
delivered and acked it (`entries-read: 1`, `pending: 0`), and confirmed
context-service actually collected real evidence for that incident
end-to-end through the new path — not the old HTTP fallback.

Also found and fixed the same Dockerfile `PYTHONPATH` bug documented earlier
in this doc for `investigation-service` — `context-service`'s Dockerfile had
the identical `/app:/libs` mistake (one directory level too deep for `import
libs.common` to resolve), invisible until this was the first thing in that
service to actually import from `libs.common.eventbus` at runtime.

### Auto-dispatch and a bounded, priority-ordered worker pool

The event bus above only replaced *one* fragile hop (incident → context
collection). The next one was arguably worse: nothing automatically
triggered investigation after context collection finished at all —
`POST /incidents/{id}/investigate` had to be called manually, per incident,
by an operator or by whatever curled it during testing. That doesn't survive
contact with real incident volume.

`context-service` now publishes a `context.collected` event after a
successful (or partial) collection (`app/services/eventbus_publish.py`).
`investigation-service` runs two kinds of background task
(`app/services/dispatch.py`), both started in its lifespan:

- **`run_dispatch_consumer`** — durably ingests `context.collected` via a
  Redis Streams consumer group and enqueues each incident into a
  Redis-backed priority queue (`RedisPriorityQueue`, a sorted set:
  `ZADD`/`ZPOPMIN`), scored by severity (`critical` first, then `warning`,
  then `info`, unknown severities last) with a timestamp tiebreaker so
  same-severity incidents still drain oldest-first. Enqueueing is near-
  instant, so this absorbs an arbitrarily large burst of incidents without
  ever blocking on investigation itself.
- **`run_investigation_worker`** × `MAX_CONCURRENT_INVESTIGATIONS` (default
  2) — a fixed-size pool that drains the priority queue and calls the exact
  same `run_investigation()` the manual HTTP route already used.

**This is a hard throughput ceiling by design, not an oversight.** LLM
investigation is compute-bound — one Ollama instance serializes generations
— so raising the worker count only helps up to what the model backend can
genuinely run concurrently; past that, workers just queue behind each other
on the same backend. The honest fix for "thousands of incidents at once" is
not more workers, it's more/faster inference capacity (a hosted API with a
real concurrent-request limit, or a fleet of Ollama instances behind
model-gateway) — this queue is what makes that scale-up meaningful instead
of cosmetic: without it, throwing more compute at the problem wouldn't help
either, because nothing would route incidents to it in priority order or
prevent unbounded concurrent LLM calls from overwhelming the backend anyway.

Two Prometheus metrics make this observable rather than a black box:
`investigation_queue_depth` (sustained growth = incoming rate exceeding
processing throughput — the signal to scale inference capacity) and
`investigations_dequeued_total{severity=...}` (proves the priority ordering
is actually happening, not just configured).

**A second, more serious auth bug found while verifying this live**: the
first real end-to-end run showed `severity: "unknown"` on the published
event for an incident that was genuinely `critical`. Traced to
`context-service` never having sent a service-mesh token when calling
`incident-service`'s `GET /incidents/{id}` — which enforces auth (Phase 7) —
so every single call had been silently 401'ing and falling back to
`{"severity": "unknown", "service": <default>, "alertname": ""}` for the
entire time auth has been enabled in the real stack, masked by a broad
`except Exception` that logged a warning and moved on rather than
surfacing it. This wasn't just wrong severity for queue ordering — it meant
every RCA's `incident-meta` evidence and every rule keyed on `alertname` was
working from degraded metadata this whole time. Fixed by adding
`internal_service_token` to context-service's config and sending
`X-Service-Token` on that call (matching the pattern `remediation-service`
already used correctly). Verified live: re-collected context for the same
incident, the republished event correctly showed `severity: "critical"`.

**Verified live, end to end, with no manual `/investigate` call**: fired a
real fault, watched the incident auto-flow through both event streams,
confirmed the priority queue and consumer groups drained correctly
(`entries-read` / `pending: 0` on both), and confirmed
`investigations_dequeued_total{severity="critical"} 1.0` — a real,
correctly-prioritized, fully automatic investigation, not a manually
triggered one.
