# Failure-attribution decision candidate — NOT AUTHOR-ACCEPTED

**AUTHOR DECISION REQUIRED. No option has been accepted.**

**FACT FROM PROTOCOL:** `prompt_development_protocol_v1.md` §7 and §10/D10
require classification/finalization evidence, one identical retry for an isolated
technical failure, no parser retry, retention, and fixed logical denominators.
Crash/OOM appears as an example of explicit runtime failure. There is no literal
requirement to induce or observe each possible crash/OOM mode. Ambiguous envelope
attribution must retain evidence and block adjudication; systematic defects block
execution. These approved rules remain unchanged.

**FACT FROM IMPLEMENTATION/EVIDENCE:** The unchanged provider distinguishes
connection/interrupted delivery, timeout, explicit HTTP 5xx, completed final
content and ambiguous envelopes. The existing capture actually observed local
connection refusal; a bounded timeout, HTTP 500, malformed completed final content
and valid content at isolated fabricated HTTP boundaries; and actual Ollama HTTP
500 rejection of an invalid `top_k` type (systematic configuration, no retry).
The nine prior fabricated native-model completions also establish normal provider
completion. They were not rerun. SQL integration tests exercise durable attempts,
identical retry bytes, parser no-retry, terminal technical failure and one logical
run despite multiple attempts. New application-login tests exercise these writes
with the actual least-privilege principal in disposable databases.

**UNOBSERVED:** A genuine Ollama worker crash, OOM, platform memory pressure, and
all possible runtime-specific error envelopes. No worker termination, host OOM,
process kill, network modification or new semantic generation was performed.
Synthetic server errors are not presented as genuine worker crashes.

**INFERENCE:** This establishes the protocol's bounded attribution requirement,
not exhaustive empirical coverage of runtime faults. The former preflight blocker
wording (“no genuine crash/OOM”) was a conservative evidence placeholder, not an
additional approved scientific criterion. The technical check now validates the
existing measured failure evidence plus source-bound SQL/test evidence. Final
Gate-B artifact acceptance still blocks on the author's explicit review of this
limitation. The historical capture and its limitation text are unchanged.

A future crash producing interrupted delivery/timeout or explicit HTTP 5xx is a
technical candidate, never a malformed semantic prediction. Its raw/partial bytes
and timestamps are retained before attribution. The post-review adapter pauses
for an explicit spool-hash-bound technical review. Only isolated attribution
allows attempt 2 with identical request/configuration/seed; a second isolated
technical failure terminates the same logical run, with no prediction. Parser
failure is terminal without retry. A missing/unusable/ambiguous envelope remains
unadjudicated and blocks; it is **not** automatically declared technical or
semantic. Completed and failed logical runs remain in the planned denominator;
a held run prevents completion/evaluation until adjudicated.

Deliberately exhausting host RAM would test one particular runtime/OS failure
path while risking unrelated SQL/data/processes. It would not establish that all
future OOM/crash envelopes are identical or isolated. A verified, exclusive,
reversible worker-termination mechanism could add useful coverage of that one
worker-exit path, but has not been established here and is not substituted with
an arbitrary process kill.

- **Option A:** accept bounded qualification and explicitly retain genuine
  worker crash/OOM as an unobserved runtime limitation in the methodology.
- **Option B:** require another separately scoped safe worker diagnostic before
  acceptance. Establish exclusive ownership and supported reversible termination
  first; if that cannot be established, retain the blocker. No host OOM.

Option B requires a new evidence/candidate revision after the diagnostic. The
current candidate's acceptance consumer only admits an explicit Option A record;
it never manufactures that record or infers a decision from elapsed time.
