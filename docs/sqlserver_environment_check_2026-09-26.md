# SQL Server disposable environment check

Recorded **2026-09-26, Europe/Berlin** (runtime evidence uses UTC on September 25).
Result: **the seven requested data/connection/recovery checks passed**, with one
corrected probe conversion defect retained below. This is limited local
compatibility evidence, not scientific deployment acceptance, vendor support,
Gate B, or acceptance of the 18-table schema / all 55 design scenarios.
Final shutdown reported exit 137; graceful shutdown remains unqualified.

## Authority and approval reconciliation

Engineering reference: research
[`database_design_v1.md`](../../bachelor_rest_api_checker/03_research_design/database_design_v1.md).
The exact P1/P2/P3 files were read and recomputed **before** status changes:

| Candidate | UTF-8 bytes | SHA-256 |
|---|---:|---|
| P1 | 4325 | `f451d8bdc89cb1f3d8a2b2dbc0c86fc490f3033d98a689a128e3f4069aad1cc6` |
| P2 | 4996 | `50bfce7831530c7d63dd469ed82fb9acab755bedf4808ae5574775fc5505594f` |
| P3 | 5835 | `5561c7d953b7baf3bfcc72f7bfeeccec2c64f11b5b4989788e227270205a94fb` |

All matched the supplied existing author decision **“Texte sind freigegeben”**.
The [separate reconciliation record](../../bachelor_rest_api_checker/03_research_design/prompt_candidates_v1/author_approval_reconciliation_2026-09-26.json)
records it at `2026-09-26T00:40:29+02:00`; the original approval date/timestamp
remain **null/unknown**. The source is the author's current task supplying the
prior decision, not an independently retrieved conversation export or a new
substantive approval. O01 is resolved; current candidate/protocol/review status
and bindings agree. Prompt/shared/output bytes and scientific policies did not
change. Four byte-exact prior documents are archived and hash-bound; historical
source hashes remain historical. Current references are acyclic.

Research HEAD at inspection was `8d87d89a7ce066773c72ea058ed7e5eb9a4cf9b4`;
design, protocol and candidates were already untracked. Their later addition to
Git does not imply they existed at that HEAD. Technical baseline was
`6ea0a37a8ccf4bf5ce1ebecc5113a3a5eb51e4de`. Verification is in
[`13_approval_verification.json`](sqlserver_environment_evidence/13_approval_verification.json).

## Exact observed stack

| Component | Actual observation |
|---|---|
| Host | macOS 27.0, build 26A428; Apple M5 Pro, arm64; 68,719,476,736 bytes RAM |
| Docker Desktop | 4.92.0 (240144); `desktop-linux` context |
| Docker client / engine | Both 29.8.0, API 1.56; client darwin/arm64, server linux/arm64; commits 88096ef / 3ce5872 |
| Compose / containerd / runc | v5.5.1 / v2.3.5 / 1.5.1 |
| Docker VM | Linux 7.0.12-linuxkit, aarch64, 18 CPUs, 8,317,267,968 bytes RAM; overlayfs, cgroup v2 |
| Engine | SQL Server 2022 RTM-CU27, KB5104824, **16.0.4295.3**, Developer Edition (64-bit), X64; build Aug 26 2026 |
| Container OS / platform | Ubuntu 22.04.5 LTS; `linux/amd64`; container `uname -m` = x86_64 |
| Native Python | Project `.venv/bin/python`, **3.12.14**, Clang 22.1.3; arm64 |
| Python bridge / manager | **pyodbc 5.3.0**, arm64 Mach-O extension; uv 0.12.18 |
| Native ODBC | **Microsoft Driver 18.7.1.1**, arm64; runtime SQL_DRIVER_VER `18.07.0001`; unixODBC **2.3.14**, SQL_ODBC_VER `03.52` |
| Driver path | `/opt/homebrew/lib/libmsodbcsql.18.dylib`; registration in `/opt/homebrew/etc/odbcinst.ini` |

Resolved available concrete tag: `mcr.microsoft.com/mssql/server:2022-CU27-ubuntu-22.04`.
Compose actually uses the immutable full binding:

```text
mcr.microsoft.com/mssql/server@sha256:4402d880dd4c34bfa7d8705e56a86cd6c88da80a1f6bbbe741f999e76264a090
```

Registry inspection, pull and local image inspection agreed. No `latest` tag was
used. Host preflight found the daemon running and **zero containers, images and
volumes**. Initial sandbox access to the Docker socket was denied; authorized
execution outside the sandbox established the real daemon state. No pre-existing
Docker resource was modified. The native driver/manager/pyodbc were absent and
installed through approved execution permissions. Only missing Homebrew
dependencies m4 1.4.21, libtool 2.6.2 and unixODBC were installed; existing
OpenSSL 3.6.4 was retained. Automatic updates/cleanup were disabled.

The precise Docker VMM/Rosetta toggle is **unverified**: macOS denied access to
`settings-store.json` even outside the sandbox, and read-only UI inspection timed
out. Architecture observations establish amd64 execution on an arm64 VM; they do
not identify the emulator. No Docker/emulation or host security settings changed.
Microsoft supports these engine containers on Linux x86-64 hosts and excludes
emulation/translation environments; a successful local probe does not change
that boundary. [Microsoft container support](https://learn.microsoft.com/en-us/sql/linux/containers/deploy?view=sql-server-ver16)

Connections used native host Python/ODBC over TCP `127.0.0.1:14339`, SQL
authentication, `Encrypt=yes;TrustServerCertificate=yes`, 10-second login timeout
and 60-second query timeout. The server reported TCP / encrypted TRUE / SQL auth.
Certificate identity was intentionally not validated for this disposable
self-signed local service; no host trust store was changed. The negotiated TLS
protocol/cipher was not measured. The administrative login is probe-only, not a
proposed application login. Passwords remain in an external mode-0600 file and
were checked absent from retained report/evidence files.

## Executed checks and evidence

Only `dbo.probe_parent`, `dbo.probe_value` and one session-local `#probe_unique`
table were created. Fixtures are fabricated; none comes from DEV, prompts or API
observations.

| Requested check | Result and observations |
|---|---|
| 1. Host application connection | PASS via native Python/pyodbc/Driver 18; no container-only sqlcmd substitute |
| 2. Exact VARBINARY(MAX) | PASS for empty bytes, malformed JSON (10 bytes), invalid UTF-8 (4 bytes), and 1,048,593 bytes; retrieved bytes equal originals; original, retrieved and SQL SHA2_256 hashes agree |
| 3. Typed round-trips | PASS for multilingual/emoji/composed and decomposed Unicode, CRLF/tab/trailing spaces, empty and 34,816-byte UTF-16 text; exact DECIMAL values and scale; 7-digit fractional timestamps with +05:45, -03:30, +00:00, +02:00 offsets; BIT false, true and NULL remain distinct |
| 4. Constraints | PASS: wrong composite pair rejected despite both IDs existing; duplicate primary and independent UNIQUE keys rejected; required NULL rejected; all 3 legal verdicts retained; 11 malformed/NULL verdict inputs rejected, including wrong case, spaces and tab; SQLSTATE 23000 and expected 547/2627/515 diagnostics |
| 5. Transactions | PASS: commit visible through another connection; rollback removes an insert and reverses an update; no unintended rows/values survive |
| 6. Restart | PASS: dedicated `docker restart`, then host-side re-read; three parent rows, four child rows, all values/hashes and trusted/enabled FK/CHECK state match |
| 7. Backup / separate restore | PASS: COPY_ONLY/CHECKSUM backup, VERIFYONLY, external copy and separate restore; original unchanged, all rows/relationships/values/hashes identical |

The [first probe record](sqlserver_environment_evidence/01_initialize.json) is
**FAIL**, retained unchanged: SQL style-127 output conversion normalized a stored
offset to UTC. [Native-field diagnosis](sqlserver_environment_evidence/02_timestamp_diagnostic.json)
proved the stored value still had its original offset and nanosecond field.
The probe was corrected to decode `SQL_SS_TIMESTAMPOFFSET` directly, retaining
100 ns precision instead of converting to Python's microsecond datetime. No
fixture, database value or expected timestamp was changed. The subsequent
[read-back](sqlserver_environment_evidence/03_native_roundtrip.json),
[restart](sqlserver_environment_evidence/05_after_restart_roundtrip.json), and
[restore](sqlserver_environment_evidence/09_restore.json) snapshots are identical.
This is an engineering probe correction, not an experimental setting change.
The [source correction patch](sqlserver_environment_evidence/02_probe_offset_correction.patch)
also records the later backup-file guard and independent UNIQUE probe addition.
Original probe SHA-256: `f096d7f018ffcfe4e40504185a34a122ac3a90c621c318d395934cb39d02e48f`.
Final probe SHA-256: `316636174ae61f06d906995ac06d27d52daf6f23e8c89c4139ddf9280e0b1e58`.
The native structure is documented by
[Microsoft](https://learn.microsoft.com/en-us/sql/relational-databases/native-client-odbc-date-time/data-type-support-for-odbc-date-and-time-improvements?view=sql-server-ver15).

Four focused converter regression tests passed, including a negative sub-hour
offset and explicit rejection of unrepresentable precision. The full repository
suite/Q01–Q26 were **not executed**, because this task expressly prohibits Oracle
execution. Oracle code/tests and all study data remain untouched; older suite
results are not presented as fresh results.

## Backup and retained resources

External backup: `/private/tmp/rac-sqlserver-environment-20260926/rac_env_probe_20260926.bak`,
**4,640,768 bytes**, mode **0600**, SHA-256:
`277b52a929fef90d92bb8fe5c26c0b620eb7d89572ede7141861189fe37cfb55`.
It matches both the original in-container backup and the host copy re-imported
as `host_copy_for_restore.bak`. The re-imported file initially belonged to root
and was unreadable by mssql; changing ownership on **that file only**, keeping
0600, resolved the diagnostic before restore. No host-wide permission changed.
Restore created `rac_env_probe_restore_20260926` with separate MDF/LDF paths and
no `REPLACE`; it did not overwrite `rac_env_probe_20260926`.

Retained resources: Compose project `rac-sql-env-20260926`; container
`rac-sql-env-20260926-sqlserver-1`; network `rac-sql-env-20260926_default`; named
volume `rac-sql-env-20260926_probe_data` mounted at `/var/opt/mssql`; both test
databases, two backup files in that volume, the pinned image, and the private host
directory containing credentials, backup and full container log. Host driver,
dependencies and project pyodbc installation remain installed.

The container was stopped after all comparisons. Final state is **exited 137,
OOMKilled=false**, with no Docker error string. A graceful shutdown was not
established, and no post-final-stop recovery check was run. The earlier requested
restart and independent restore passed; they do not erase this later operational
limitation. Shutdown state/tail are retained in evidence files `12_*`.

Safe cleanup instructions are in the [probe README](../tools/sqlserver_environment/README.md#safe-cleanup-after-evidence-retention).
`docker compose --env-file <external-file> -f tools/sqlserver_environment/compose.yaml down --volumes`
removes only this project's container/network/volume after checking their labels
and retaining needed evidence. It was **not run**. Do not globally prune. The
external backup is outside Git/container, but `/private/tmp` is not durable archival
retention; retain it elsewhere explicitly if needed before later cleanup.

## Commands actually executed

Preflight: `sw_vers`, `uname -m`, `sysctl`, Docker app Info.plist version reads,
`docker version`, `docker context show`, `docker compose version`, `docker info`,
`docker ps -a`, `docker volume ls`, `docker images --digests`, `brew list --versions`,
PyCharm `get_python_environment`, native Python/package/architecture checks,
`odbcinst -j/-q`, and Mach-O `file` checks. Docker settings file read and UI
inspection were attempted but unavailable, as above.

Installation/resolution: Microsoft's MCR `/v2/mssql/server/tags/list`,
`docker buildx imagetools inspect ...:2022-CU27-ubuntu-22.04`, `docker pull --platform linux/amd64 <full-digest>`,
`docker image inspect`; `brew tap microsoft/mssql-release`, `brew info`,
`brew install ... --dry-run`, then `brew install microsoft/mssql-release/msodbcsql18`
with `HOMEBREW_NO_AUTO_UPDATE=1`, `HOMEBREW_NO_INSTALL_CLEANUP=1`,
`HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1`, `HOMEBREW_ACCEPT_EULA=Y`;
PyPI version lookup and `uv add --group sqlserver-probe 'pyodbc==5.3.0'`.

Execution: private credential generation and socket-bind port check;
Compose `config --quiet` and `up -d`; host `.venv/bin/python tools/sqlserver_environment/probe.py`
phases **initialize → read-only timestamp diagnosis → verify → container restart
→ verify → backup → external docker cp/hash check → restore → unique**.
Each phase used the external env file and a fresh evidence path. The SQL is fully
visible in the [small probe script](../tools/sqlserver_environment/probe.py).
The backup directory creation, scoped restore-file `chown`, `sha256sum`/`shasum`,
container OS/version/log/resource inspection and final `docker stop` are recorded
above. Tests: `.venv/bin/python -m unittest discover -s tools/sqlserver_environment -p test_probe.py -v`.
No cleanup/prune command was executed.

Final offline verification: `uv lock --check --offline` passed. Technical
`git diff --cached --check` passed. Research reconciliation diffs introduce no
whitespace errors; its newly tracked baseline/design snapshot retain six reported
Markdown hard-break lines (three original lines in each copy), deliberately not
rewritten. Current/historical artifact hashes, unchanged scientific protocol
sections and absence of the generated password from staged files were checked.
Captured log text is preserved losslessly inside JSON wrappers; raw copies remain
outside Git. [Evidence index](sqlserver_environment_evidence/manifest.json) binds
the report, probe/configuration, dependency files and captured evidence by hash.

## Remaining prerequisites and proposed next binding

The next task still needs explicit schema/persistence authorization. Resolve and
record acceptance of the unsupported emulated engine deployment separately from
this compatibility result; confirm the exact Docker VMM/emulation setting and
qualify graceful stop/recovery behavior before relying on the local service.
No remote host or alternative database engine was substituted.

Propose retaining **Python 3.12.14 + pyodbc 5.3.0 + unixODBC 2.3.14 + Microsoft
ODBC 18.7.1.1** and the exact CU27 digest above as the starting engineering
binding, subject to that deployment decision. Use explicit parameterized SQL
and an offset/precision-preserving timestamp adapter; reject excess numeric/text
precision before conversion. Production certificate identity and least-privilege
application credentials remain to be specified/tested. This task did not accept
self-signed administrative probe settings for scientific execution.

Migration proposal remains the reviewed minimum: technical-repository-owned,
immutable numbered T-SQL files, SHA-256/version ledger, explicit apply command,
exclusive migration lock and tested transactional failure behavior; runtime only
checks compatibility. No ORM or migration framework has been installed or
implemented. All domain-schema/import/lifecycle/recovery acceptance work remains
future work; these probes do not claim all DB01–DB55 passed.

No DEV import/rematerialization, Oracle execution/reference changes, Ollama
inspection/call/inference, runner/parser/evaluator/UI implementation, model
comparison or study execution occurred. Gate B and final prompt freeze remain
incomplete. **Stop at this report.**
