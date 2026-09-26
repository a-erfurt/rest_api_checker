# SQL Server persistence

The author authorized this stage after accepting the qualified local deployment,
including its documented emulation limitation. Authority:
[`database_design_v1.md`](../../bachelor_rest_api_checker/03_research_design/database_design_v1.md),
including the implementation correction in §14. Scientific decisions, D01–D11,
Oracle semantics, dataset split, prompts and sampling settings remain unchanged.
**No LLM experiment has run.** This package contains no provider dispatch,
renderer, model-output parser, evaluator or UI. Synthetic test outcomes are
explicitly fabricated persistence fixtures, not model results.

## Schema and migrations

`src/rest_api_checker/persistence/migrations/001_application_schema.sql` creates
all 18 application tables and 34 NO ACTION foreign keys. The evidence path is
files → contracts/operations and responses → cases → reference revisions →
dataset memberships → experiment schedule → attempts → predictions. Models,
prompts and configurations bind each planned run. Reports retain separate input
and result artifacts. `datasets` has exactly id/name/version/purpose.

All application primary keys are BIGINT IDENTITY clustered keys; alternate and
unique keys are nonclustered. Five composite FKs prove reference/case,
experiment/dataset, membership/dataset, attempt/request and prediction/attempt/run
agreement. Original bytes use VARBINARY(MAX), SHA-256 and computed DATALENGTH.
Files reject UPDATE/DELETE even through an administrative SQL statement.

Machine tokens use BIN2 and exact byte lengths. SQL Server can discard excess
trailing blanks before a CHECK: verdict columns therefore have **VARCHAR(15)**
rejection headroom, while NOT_APPLICABLE must still have exactly 14 bytes. This
is the sole correction to the reviewed physical design. Reference vectors retain
the four qualified combinations; predictions admit all 27 legal combinations.
Bounded strings are checked in UTF-16 units (or ASCII bytes) before binding;
excess Decimal scale is rejected before conversion. SQL row checks do not
replace source, lifecycle, parser or profile validation.

Migration 002 creates `rac_application`: SELECT, explicit INSERT grants,
restricted operational-column UPDATE grants, no DELETE/schema alteration or
ledger write. Immutable evidence has no update API. Lifecycle predicates on the
operational columns are enforced transactionally by the repository; ordinary
FKs or role membership alone do not enforce the full write policy. Administrative
credentials can bypass application policy and must not be used by a future
runner. Provision a separate SQL login/user outside Git, then add its database
user to `rac_application`. No login or password is embedded in a migration.

The additional `schema_migrations` ledger is not a domain table. Explicit apply
uses an exclusive transaction-owned application lock, contiguous numbered files,
SHA-256, expected-current-version checking, and one transaction for pending
migrations plus ledger inserts. Matching reapplication is a no-op; changed
checksums, gaps, unknown versions, wrong expected version, lock failure and
unledgered nonempty databases fail. Failed migration batches roll back both DDL
and ledger. `Repository` verifies compatibility and checksums and never migrates.
Keep applied migration bytes unchanged; add a reviewed next version instead.
Migrations touching used evidence require a reviewed plan and verified backup.

SQL references: [application locks](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-getapplock-transact-sql?view=sql-server-ver16),
[transaction abort behavior](https://learn.microsoft.com/en-us/sql/t-sql/statements/set-xact-abort-transact-sql?view=sql-server-ver16),
[CHECK and UNIQUE constraints](https://learn.microsoft.com/en-us/sql/relational-databases/tables/unique-constraints-and-check-constraints?view=sql-server-ver16).

## Qualified local service

Reuse `tools/sqlserver_environment/compose.yaml`, Docker Desktop, its isolated
`rac-sql-env-20260926` project, persistent named volume and localhost port 14339.
The pinned image is:

```text
mcr.microsoft.com/mssql/server@sha256:4402d880dd4c34bfa7d8705e56a86cd6c88da80a1f6bbbe741f999e76264a090
```

It is SQL Server 2022 Developer CU27. The qualified client is Python 3.12,
pyodbc 5.3.0 and Microsoft ODBC Driver 18. The local connection explicitly uses
Encrypt=yes, TrustServerCertificate=yes and LongAsMax=yes. Certificate identity
is not validated in this local environment; this is not a deployment-wide trust
change. Credentials remain in a mode-0600 file outside Git. Optional
`RAC_SQL_USER` selects a separately provisioned application login; omission uses
`sa` only for local administration/tests. Do not print credentials or rendered
Compose configuration. ODBC pooling is disabled to make connection lifetime and
safe disposable cleanup explicit.

```sh
RAC_ENV=/private/tmp/rac-sqlserver-environment-20260926/credentials.env
RAC_COMPOSE=tools/sqlserver_environment/compose.yaml
docker compose --env-file "$RAC_ENV" -f "$RAC_COMPOSE" config --quiet
docker compose --env-file "$RAC_ENV" -f "$RAC_COMPOSE" start sqlserver
# Check readiness with the CLI version command after an initialized database exists.
docker compose --env-file "$RAC_ENV" -f "$RAC_COMPOSE" stop sqlserver
```

Do not modify global Docker/emulation settings or run global prune/reset commands.
The Apple-Silicon emulated engine is outside Microsoft vendor support; the author
accepted this limitation for the local implementation task. The earlier exit-137
shutdown (not OOM) remains a known graceful-stop limitation, not evidence of
corruption. Stop work on actual instability, corruption or restore failure. See
[qualification report](sqlserver_environment_check_2026-09-26.md) for historical
observations and unresolved emulator details. This task leaves the reused
container running; it does not destroy the qualified volume or original probes.

## Explicit administration

Run from the technical repository root using the configured Python 3.12 venv.
Install locked dependencies with `uv sync --locked`; pyodbc is now a runtime
dependency. Migration files ship inside the persistence package.

```sh
.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" init
.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" migrate --expected-current 0
.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" version
# Identical second apply, with the actual current version explicitly supplied:
.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" migrate --expected-current 2
```

`init` creates an absent `rest_api_checker` database; it refuses to reset an
existing one. The implementation verification used disposable databases only;
these commands do not imply a persistent study database has been populated.

```sh
RAC_TEST_DB=$(.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" create-test)
.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" --database "$RAC_TEST_DB" migrate --expected-current 0
.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" --database "$RAC_TEST_DB" version
# Close clients first. Only a rac_test_<32 hex> database carrying the test marker can be dropped.
.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" --database "$RAC_TEST_DB" destroy-test
```

No command forcibly disconnects other clients, deletes Docker volumes, or drops
the real/probe databases. A failed cleanup is visible and requires inspecting
the named resource; it is never replaced by a global reset.

## Released source import

Existing staging is mandatory. Missing/mismatched artifacts stop import; the
importer never regenerates, mutates or remeasures cases. It explicitly maps native
`development-dataset-v1` to `development_dataset` / `v1` / `development` and local
reference revision 1. The complete manifest, sidecar, release, current release
authority, contracts, bodies, envelopes, replacements and source companions are
archived. Historical implementation/version hashes remain source assertions in
the original manifest; current code is not substituted for historical bytes.

```sh
RAC_RESEARCH=/Users/aerfurt/University/Bachelor/bachelor_rest_api_checker
.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" --database "$RAC_TEST_DB" import-dev \
  --staging artifacts/development_dataset_v1 \
  --release docs/development_dataset_v1_release.json --research "$RAC_RESEARCH"
.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" --database "$RAC_TEST_DB" import-prompts \
  --research "$RAC_RESEARCH"
```

Import returns stable IDs and a file map. An immutable import receipt binds
portable paths/hashes, local IDs and adapter hash without adding dataset columns.
Every DEV membership binds an explicit reference revision, preserving ordering,
origins, native parent families and immediate parents. The reference source
pointer preserves the full original Oracle record. `verification_target` is
archived, never used for labels. Body, response.json and response-v1 envelope
hashes remain different identities. Equal bodies may share a file; separate
observations keep different response/case rows. Identical re-import is idempotent;
changed content under an admitted identity is rejected, never upserted.

Prompt import validates the candidate manifest and existing approval record,
archives current protocol/review/shared/history artifacts, and maps P1/P2/P3 to
direct/checklist/explicit with explicit version v1. It stores each complete
approved instruction verbatim and does not concatenate shared blocks again.
Neither import creates models, experiments, runs or outputs.

## Write API and recovery

`database.py` supplies connections, exact bounds and a native DATETIMEOFFSET
converter preserving offset and seven fractional digits. A source date or unknown
time remains in source bytes; it is not coerced to midnight. DEV observed_at is
the recorded request/acquisition time, not an invented response-receipt time.

`repository.py` implements files, APIs/contracts/operations, families/responses/
cases, append-only reference revisions, datasets/memberships, models, prompts,
configurations, atomic caller-supplied schedules, reservations, finalization,
diagnostic successors and report metadata. Each public write is transactional;
`with repo.transaction():` groups writes. Nested failures make the transaction
rollback-only. One repository/connection belongs to one thread.

`archive(name, bytes)` compares actual bytes on hash reuse; `file(id)` verifies
hash and size when retrieving. `source(id, pointer)` resolves original records.
`archive.export_files` writes a new hash-addressed byte directory and preserves
path/role aliases in its manifest; it never interprets source paths as export
paths or overwrites a prior export.

`plan_experiment` persists the supplied complete schedule and its snapshot in one
transaction. It verifies memberships, explicit complete references, source
projections and supplied closure. It does not generate a schedule or certify
Gate B. Full setup/model/template/renderer preflight remains future work; final
evaluation admission is explicitly blocked until that stage exists.

`reserve` locks a logical run, fixes request bytes and commits a slot. An existing
slot is a reconciliation condition, not permission to send again. Reservation
only sets prepared_at; `observe_start` requires a genuinely observed start.
Attempt 2 requires recorded qualifying first-attempt technical failure and exact
request reuse. There is no attempt 3. A nonqualifying or ambiguous first failure
leaves the run unresolved. Provider classification and dispatch remain absent.

`finalize` takes an explicitly adjudicated outcome and parsed prediction from a
future parser. It binds diagnostics to the frozen parser/request/run/attempt,
archives exact response bytes (including NULL versus empty), and settles the
attempt/prediction/run atomically. Legal but wrong vectors remain valid stored
predictions. Parser/technical failures have no prediction. A first technical
failure preserves a pending run; the second settles it. Identical finalization
replay is a no-op; conflicts block. Completed responses/results/predictions cannot
be replaced. `append_diagnostics` requires the current predecessor ID and retains
a hash-linked immutable successor for late evidence. A failed compare-and-swap
requires rebuilding from the latest predecessor.

`spool.stage` writes a versioned checksum envelope containing run/attempt IDs,
request/setup hashes, exact base64-encoded response bytes, transport evidence and
only supplied observed times. It fsyncs a private temporary file, publishes through
an atomic no-clobber hard link, then fsyncs the directory. Identical staging is a
no-op; failure raises and preserves available bytes. This requires a local
filesystem supporting hard links. The receipt-to-fsync loss window remains.
`spool.reconcile` verifies identity/checksums and archives evidence idempotently.
Without an outcome it preserves unresolved state; with an explicit caller-supplied
outcome it replays transactional finalization. It never reserves another attempt,
parses an answer or calls a provider. Files are retained after import. Late evidence
advances only diagnostics, never the original response or verdict.

`report` stores metadata for a caller-produced completed analysis and validates
basic source/reference relationships. Report formulas, full analysis-input set
reconciliation, sensitivity pairing and approved correction authority checks are
not implemented here. New reference/report rows preserve the old memberships,
outcomes and reports. This metadata API is not a completed evaluator.

## Backup and restore

A volume is not a backup. Choose a new lowercase 32-hex token and absent server
path; the backup helper requires this isolated filename and refuses overwrite.
Use the administrative credentials only for these commands.

```sh
RAC_BACKUP=/var/opt/mssql/backup/rac_persistence_<32_hex_token>.bak
RAC_HOST_BACKUP=/private/tmp/rac-sqlserver-persistence-20260926/<same_filename>.bak
docker exec rac-sql-env-20260926-sqlserver-1 mkdir -p /var/opt/mssql/backup
.venv/bin/python -m rest_api_checker.persistence --env-file "$RAC_ENV" --database "$RAC_TEST_DB" backup --server-path "$RAC_BACKUP"
# Ensure the external target is absent, then copy and retain it privately.
docker cp "rac-sql-env-20260926-sqlserver-1:$RAC_BACKUP" "$RAC_HOST_BACKUP"
chmod 600 "$RAC_HOST_BACKUP"
shasum -a 256 "$RAC_HOST_BACKUP"
docker exec rac-sql-env-20260926-sqlserver-1 sha256sum "$RAC_BACKUP"
```

For independent recovery, copy that host file back under a **different absent**
`rac_persistence_<32_hex>.bak` server path, set only that file's ownership to
`mssql` (mode 0600), and compare all hashes. `restore-test --server-path <copy>`
performs CHECKSUM verification and restores into a new marked disposable database
with separate MDF/LDF paths, never REPLACE. Compare every table/relationship/hash,
then explicitly destroy only that disposable target. Retain host backup and
credentials outside Git; `/private/tmp` is not a long-term retention policy.

## Verification command and stage boundary

```sh
RAC_SQL_TEST_ENV="$RAC_ENV" \
RAC_SQL_TEST_BACKUP_DIR=/private/tmp/rac-sqlserver-persistence-20260926 \
.venv/bin/python -m pytest tests tools/sqlserver_environment/test_probe.py -q
```

Without RAC_SQL_TEST_ENV, SQL integration tests are explicitly skipped. Without
RAC_SQL_TEST_BACKUP_DIR, the Docker-copy/restore test is skipped. A passing local
unit suite alone is not SQL acceptance. Tests create and destroy marked temporary
databases; they retain external backups and no study database. The backup test
uses the exact qualified container name/digest and never global Docker cleanup.

See [verification and acceptance matrix](persistence_verification_2026-09-26.md)
for actual results, deferred portions and limitations. The existing full suite
includes Oracle qualification and synthetic fixture construction tests; these
are regression checks, not importer remeasurement of the released DEV data.
