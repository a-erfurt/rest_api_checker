# Actual pre-change help captures

Every block below was executed with `PYTHONDONTWRITEBYTECODE=1` and exited 0. No DB connection, provider request or migration was run.

## .venv/bin/rest-api-checker --help

```text
usage: rest-api-checker [-h] [--json] [--plain] [--verbose]
                        [--env-file ENV_FILE] [--database DATABASE]
                        [--root ROOT] [--research RESEARCH]
                        {db,dataset,experiment,evaluate,inspect,preflight,service}
                        ...

Thesis CLI: bounded SQL inspection, immutable evaluation and offline
preflight.

positional arguments:
  {db,dataset,experiment,evaluate,inspect,preflight,service}

options:
  -h, --help            show this help message and exit
  --json                JSON only on stdout
  --plain               No color or animation
  --verbose
  --env-file ENV_FILE   Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker db --help

```text
usage: rest-api-checker db [-h]
                           {status,version,init,create-test,destroy-test,migrate,backup,restore-test,import-dev,import-prompts}
                           ...

positional arguments:
  {status,version,init,create-test,destroy-test,migrate,backup,restore-test,import-dev,import-prompts}

options:
  -h, --help            show this help message and exit
```

## .venv/bin/rest-api-checker db status --help

```text
usage: rest-api-checker db status [-h] [--json] [--plain] [--verbose]
                                  [--env-file ENV_FILE] [--database DATABASE]
                                  [--root ROOT] [--research RESEARCH]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker db version --help

```text
usage: rest-api-checker db version [-h] [--json] [--plain] [--verbose]
                                   [--env-file ENV_FILE] [--database DATABASE]
                                   [--root ROOT] [--research RESEARCH]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker db init --help

```text
usage: rest-api-checker db init [-h] [--json] [--plain] [--verbose]
                                [--env-file ENV_FILE] [--database DATABASE]
                                [--root ROOT] [--research RESEARCH]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker db create-test --help

```text
usage: rest-api-checker db create-test [-h] [--json] [--plain] [--verbose]
                                       [--env-file ENV_FILE]
                                       [--database DATABASE] [--root ROOT]
                                       [--research RESEARCH]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker db destroy-test --help

```text
usage: rest-api-checker db destroy-test [-h] [--json] [--plain] [--verbose]
                                        [--env-file ENV_FILE]
                                        [--database DATABASE] [--root ROOT]
                                        [--research RESEARCH]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker db migrate --help

```text
usage: rest-api-checker db migrate [-h] [--json] [--plain] [--verbose]
                                   [--env-file ENV_FILE] [--database DATABASE]
                                   [--root ROOT] [--research RESEARCH]
                                   --expected-current EXPECTED_CURRENT

options:
  -h, --help            show this help message and exit
  --json                JSON only on stdout
  --plain               No color or animation
  --verbose
  --env-file ENV_FILE   Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --expected-current EXPECTED_CURRENT
```

## .venv/bin/rest-api-checker db backup --help

```text
usage: rest-api-checker db backup [-h] [--json] [--plain] [--verbose]
                                  [--env-file ENV_FILE] [--database DATABASE]
                                  [--root ROOT] [--research RESEARCH]
                                  --server-path SERVER_PATH

options:
  -h, --help            show this help message and exit
  --json                JSON only on stdout
  --plain               No color or animation
  --verbose
  --env-file ENV_FILE   Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --server-path SERVER_PATH
```

## .venv/bin/rest-api-checker db restore-test --help

```text
usage: rest-api-checker db restore-test [-h] [--json] [--plain] [--verbose]
                                        [--env-file ENV_FILE]
                                        [--database DATABASE] [--root ROOT]
                                        [--research RESEARCH] --server-path
                                        SERVER_PATH

options:
  -h, --help            show this help message and exit
  --json                JSON only on stdout
  --plain               No color or animation
  --verbose
  --env-file ENV_FILE   Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --server-path SERVER_PATH
```

## .venv/bin/rest-api-checker db import-dev --help

```text
usage: rest-api-checker db import-dev [-h] [--json] [--plain] [--verbose]
                                      [--env-file ENV_FILE]
                                      [--database DATABASE] [--root ROOT]
                                      [--research RESEARCH] --staging STAGING
                                      --release RELEASE

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --staging STAGING
  --release RELEASE
```

## .venv/bin/rest-api-checker db import-prompts --help

```text
usage: rest-api-checker db import-prompts [-h] [--json] [--plain] [--verbose]
                                          [--env-file ENV_FILE]
                                          [--database DATABASE] [--root ROOT]
                                          [--research RESEARCH]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker dataset --help

```text
usage: rest-api-checker dataset [-h] {list,cases,inventory} ...

positional arguments:
  {list,cases,inventory}

options:
  -h, --help            show this help message and exit
```

## .venv/bin/rest-api-checker dataset list --help

```text
usage: rest-api-checker dataset list [-h] [--json] [--plain] [--verbose]
                                     [--env-file ENV_FILE]
                                     [--database DATABASE] [--root ROOT]
                                     [--research RESEARCH]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker dataset cases --help

```text
usage: rest-api-checker dataset cases [-h] [--json] [--plain] [--verbose]
                                      [--env-file ENV_FILE]
                                      [--database DATABASE] [--root ROOT]
                                      [--research RESEARCH]
                                      dataset_id

positional arguments:
  dataset_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker dataset inventory --help

```text
usage: rest-api-checker dataset inventory [-h] [--json] [--plain] [--verbose]
                                          [--env-file ENV_FILE]
                                          [--database DATABASE] [--root ROOT]
                                          [--research RESEARCH]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker experiment --help

```text
usage: rest-api-checker experiment [-h]
                                   {list,show,schedule,progress,run,resume,reconcile,demo,run-batch,batch-status,demo-batch}
                                   ...

positional arguments:
  {list,show,schedule,progress,run,resume,reconcile,demo,run-batch,batch-status,demo-batch}

options:
  -h, --help            show this help message and exit
```

## .venv/bin/rest-api-checker experiment list --help

```text
usage: rest-api-checker experiment list [-h] [--json] [--plain] [--verbose]
                                        [--env-file ENV_FILE]
                                        [--database DATABASE] [--root ROOT]
                                        [--research RESEARCH]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker experiment show --help

```text
usage: rest-api-checker experiment show [-h] [--json] [--plain] [--verbose]
                                        [--env-file ENV_FILE]
                                        [--database DATABASE] [--root ROOT]
                                        [--research RESEARCH]
                                        experiment_id

positional arguments:
  experiment_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker experiment schedule --help

```text
usage: rest-api-checker experiment schedule [-h] [--json] [--plain]
                                            [--verbose] [--env-file ENV_FILE]
                                            [--database DATABASE]
                                            [--root ROOT]
                                            [--research RESEARCH]
                                            experiment_id

positional arguments:
  experiment_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker experiment progress --help

```text
usage: rest-api-checker experiment progress [-h] [--json] [--plain]
                                            [--verbose] [--env-file ENV_FILE]
                                            [--database DATABASE]
                                            [--root ROOT]
                                            [--research RESEARCH]
                                            experiment_id

positional arguments:
  experiment_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker experiment run --help

```text
usage: rest-api-checker experiment run [-h] [--json] [--plain] [--verbose]
                                       [--env-file ENV_FILE]
                                       [--database DATABASE] [--root ROOT]
                                       [--research RESEARCH] [--fabricated]
                                       --spool SPOOL
                                       experiment_id

positional arguments:
  experiment_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --fabricated         Only marked disposable demo experiments can execute in
                       this stage
  --spool SPOOL
```

## .venv/bin/rest-api-checker experiment resume --help

```text
usage: rest-api-checker experiment resume [-h] [--json] [--plain] [--verbose]
                                          [--env-file ENV_FILE]
                                          [--database DATABASE] [--root ROOT]
                                          [--research RESEARCH] [--fabricated]
                                          --spool SPOOL
                                          experiment_id

positional arguments:
  experiment_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --fabricated         Only marked disposable demo experiments can execute in
                       this stage
  --spool SPOOL
```

## .venv/bin/rest-api-checker experiment reconcile --help

```text
usage: rest-api-checker experiment reconcile [-h] [--json] [--plain]
                                             [--verbose] [--env-file ENV_FILE]
                                             [--database DATABASE]
                                             [--root ROOT]
                                             [--research RESEARCH]
                                             --spool-file SPOOL_FILE
                                             [--fabricated]

options:
  -h, --help            show this help message and exit
  --json                JSON only on stdout
  --plain               No color or animation
  --verbose
  --env-file ENV_FILE   Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --spool-file SPOOL_FILE
  --fabricated
```

## .venv/bin/rest-api-checker experiment demo --help

```text
usage: rest-api-checker experiment demo [-h] [--json] [--plain] [--verbose]
                                        [--env-file ENV_FILE]
                                        [--database DATABASE] [--root ROOT]
                                        [--research RESEARCH] [--keep]
                                        [--delay DELAY] [--export EXPORT]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --keep               Retain marked demo database and spool for
                       inspection/resume
  --delay DELAY        Fabricated provider delay per attempt, seconds
  --export EXPORT      New directory for fabricated input/report JSON; never
                       overwrite
```

## .venv/bin/rest-api-checker experiment run-batch --help

```text
usage: rest-api-checker experiment run-batch [-h] [--json] [--plain]
                                             [--verbose] [--env-file ENV_FILE]
                                             [--database DATABASE]
                                             [--root ROOT]
                                             [--research RESEARCH]
                                             --dataset-id DATASET_ID
                                             [--spool SPOOL] [--resume]
                                             [--dry-run | --yes]
                                             experiment_id

positional arguments:
  experiment_id

options:
  -h, --help            show this help message and exit
  --json                JSON only on stdout
  --plain               No color or animation
  --verbose
  --env-file ENV_FILE   Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --dataset-id DATASET_ID
                        Exact materialized dataset ID; never latest
  --spool SPOOL         Durable attempt spool directory (required for
                        execution)
  --resume              Skip completed runs in this exact persisted experiment
  --dry-run             Complete real preflight; no model calls or prediction
                        writes
  --yes                 Confirm execution without interactive input
```

## .venv/bin/rest-api-checker experiment batch-status --help

```text
usage: rest-api-checker experiment batch-status [-h] [--json] [--plain]
                                                [--verbose]
                                                [--env-file ENV_FILE]
                                                [--database DATABASE]
                                                [--root ROOT]
                                                [--research RESEARCH]
                                                --dataset-id DATASET_ID
                                                experiment_id

positional arguments:
  experiment_id

options:
  -h, --help            show this help message and exit
  --json                JSON only on stdout
  --plain               No color or animation
  --verbose
  --env-file ENV_FILE   Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --dataset-id DATASET_ID
                        Exact materialized dataset ID; never latest
```

## .venv/bin/rest-api-checker experiment demo-batch --help

```text
usage: rest-api-checker experiment demo-batch [-h] [--json] [--plain]
                                              [--verbose]
                                              [--env-file ENV_FILE]
                                              [--database DATABASE]
                                              [--root ROOT]
                                              [--research RESEARCH]
                                              [--delay DELAY]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --delay DELAY        Simulation delay per step, 0–2 seconds; no SQL or model
                       access
```

## .venv/bin/rest-api-checker evaluate --help

```text
usage: rest-api-checker evaluate [-h] {comparison,list,show,export} ...

positional arguments:
  {comparison,list,show,export}

options:
  -h, --help            show this help message and exit
```

## .venv/bin/rest-api-checker evaluate comparison --help

```text
usage: rest-api-checker evaluate comparison [-h] [--json] [--plain]
                                            [--verbose] [--env-file ENV_FILE]
                                            [--database DATABASE]
                                            [--root ROOT]
                                            [--research RESEARCH]
                                            experiment_id

positional arguments:
  experiment_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker evaluate list --help

```text
usage: rest-api-checker evaluate list [-h] [--json] [--plain] [--verbose]
                                      [--env-file ENV_FILE]
                                      [--database DATABASE] [--root ROOT]
                                      [--research RESEARCH]

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker evaluate show --help

```text
usage: rest-api-checker evaluate show [-h] [--json] [--plain] [--verbose]
                                      [--env-file ENV_FILE]
                                      [--database DATABASE] [--root ROOT]
                                      [--research RESEARCH]
                                      report_id

positional arguments:
  report_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker evaluate export --help

```text
usage: rest-api-checker evaluate export [-h] [--json] [--plain] [--verbose]
                                        [--env-file ENV_FILE]
                                        [--database DATABASE] [--root ROOT]
                                        [--research RESEARCH] --output OUTPUT
                                        report_id

positional arguments:
  report_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --output OUTPUT
```

## .venv/bin/rest-api-checker inspect --help

```text
usage: rest-api-checker inspect [-h] {run,attempts} ...

positional arguments:
  {run,attempts}

options:
  -h, --help      show this help message and exit
```

## .venv/bin/rest-api-checker inspect run --help

```text
usage: rest-api-checker inspect run [-h] [--json] [--plain] [--verbose]
                                    [--env-file ENV_FILE]
                                    [--database DATABASE] [--root ROOT]
                                    [--research RESEARCH]
                                    run_id

positional arguments:
  run_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker inspect attempts --help

```text
usage: rest-api-checker inspect attempts [-h] [--json] [--plain] [--verbose]
                                         [--env-file ENV_FILE]
                                         [--database DATABASE] [--root ROOT]
                                         [--research RESEARCH]
                                         run_id

positional arguments:
  run_id

options:
  -h, --help           show this help message and exit
  --json               JSON only on stdout
  --plain              No color or animation
  --verbose
  --env-file ENV_FILE  Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/rest-api-checker preflight --help

```text
usage: rest-api-checker preflight [-h] [--json] [--plain] [--verbose]
                                  [--env-file ENV_FILE] [--database DATABASE]
                                  [--root ROOT] [--research RESEARCH]
                                  [--experiment-id EXPERIMENT_ID]

options:
  -h, --help            show this help message and exit
  --json                JSON only on stdout
  --plain               No color or animation
  --verbose
  --env-file ENV_FILE   Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --experiment-id EXPERIMENT_ID
```

## .venv/bin/rest-api-checker service --help

```text
usage: rest-api-checker service [-h] {capture} ...

positional arguments:
  {capture}

options:
  -h, --help  show this help message and exit
```

## .venv/bin/rest-api-checker service capture --help

```text
usage: rest-api-checker service capture [-h] [--json] [--plain] [--verbose]
                                        [--env-file ENV_FILE]
                                        [--database DATABASE] [--root ROOT]
                                        [--research RESEARCH] --base-url
                                        BASE_URL --execution-origin
                                        {remote,local_original,controlled_variant}
                                        --target-id TARGET_ID --contract-id
                                        CONTRACT_ID --path
                                        {/edx/validation/body,/resistance/csv/validation/body,/resistance/txt/validation/body,/resistance/validation/file}
                                        --input INPUT --case-id CASE_ID
                                        [--filename FILENAME]

options:
  -h, --help            show this help message and exit
  --json                JSON only on stdout
  --plain               No color or animation
  --verbose
  --env-file ENV_FILE   Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
  --base-url BASE_URL   Explicit HTTP(S) service origin
  --execution-origin {remote,local_original,controlled_variant}
  --target-id TARGET_ID
                        Exact deployment/source identity supplied by the
                        operator
  --contract-id CONTRACT_ID
                        Stored OpenAPI contract ID
  --path {/edx/validation/body,/resistance/csv/validation/body,/resistance/txt/validation/body,/resistance/validation/file}
  --input INPUT
  --case-id CASE_ID
  --filename FILENAME   Optional EDX filename header or Resistance multipart
                        filename
```

## .venv/bin/rac --help

```text
usage: rac [-h] [--root ROOT] [--research RESEARCH] [--env-file ENV_FILE]
           [--database DATABASE] [--container CONTAINER]
           [--compose-project COMPOSE_PROJECT] [--host HOST] [--port PORT]
           [--admin-env-file ADMIN_ENV_FILE] [--plain] [--json]

Optional operator launcher. The explicit argparse CLI remains authoritative.

options:
  -h, --help            show this help message and exit
  --root ROOT
  --research RESEARCH
  --env-file ENV_FILE
  --database DATABASE
  --container CONTAINER
  --compose-project COMPOSE_PROJECT
  --host HOST
  --port PORT
  --admin-env-file ADMIN_ENV_FILE
  --plain
  --json

Commands: db start | db stop | web [--open] | preflight | configure.
No command: interactive menu (TTY only).
All existing commands also work, e.g. rac db status, rac evaluate list.
Defaults: CLI > RAC_* environment > ~/.config/rest-api-checker/config.toml > project defaults.
Use rest-api-checker --help for authoritative research/admin commands.
```

## .venv/bin/rac db start --help

```text
usage: rac db start [-h]

options:
  -h, --help  show this help message and exit
```

## .venv/bin/rac db stop --help

```text
usage: rac db stop [-h]

options:
  -h, --help  show this help message and exit
```

## .venv/bin/rac web --help

```text
usage: rac web [-h] [--open]

options:
  -h, --help  show this help message and exit
  --open
```

## .venv/bin/rac configure --help

```text
usage: rac configure [-h]

options:
  -h, --help  show this help message and exit
```

## .venv/bin/rest-api-checker-web --help

```text
usage: rest-api-checker-web [-h] [--env-file ENV_FILE] [--database DATABASE]
                            [--host HOST] [--port PORT]

Read-only local research web interface

options:
  -h, --help           show this help message and exit
  --env-file ENV_FILE  Existing private SQL settings file (0600)
  --database DATABASE
  --host HOST
  --port PORT
```

## .venv/bin/python -m rest_api_checker --help

```text
usage: rest-api-checker [-h] [--json] [--plain] [--verbose]
                        [--env-file ENV_FILE] [--database DATABASE]
                        [--root ROOT] [--research RESEARCH]
                        {db,dataset,experiment,evaluate,inspect,preflight,service}
                        ...

Thesis CLI: bounded SQL inspection, immutable evaluation and offline
preflight.

positional arguments:
  {db,dataset,experiment,evaluate,inspect,preflight,service}

options:
  -h, --help            show this help message and exit
  --json                JSON only on stdout
  --plain               No color or animation
  --verbose
  --env-file ENV_FILE   Private SQL connection settings
  --database DATABASE
  --root ROOT
  --research RESEARCH
```

## .venv/bin/python -m rest_api_checker.accepted_comparison --help

```text
usage: accepted_comparison.py [-h] --candidate CANDIDATE --acceptance
                              ACCEPTANCE [--env-file ENV_FILE]
                              [--experiment-id EXPERIMENT_ID] [--spool SPOOL]
                              [--technical-review TECHNICAL_REVIEW]
                              {prepare,run,reconcile}

Explicit post-review adapter for the existing comparison orchestrator. No
approval writer, prompt selection, sensitivity or main-evaluation entry point.
An unaccepted candidate cannot connect to SQL or dispatch a provider request.

positional arguments:
  {prepare,run,reconcile}

options:
  -h, --help            show this help message and exit
  --candidate CANDIDATE
  --acceptance ACCEPTANCE
  --env-file ENV_FILE
  --experiment-id EXPERIMENT_ID
  --spool SPOOL
  --technical-review TECHNICAL_REVIEW
```

## .venv/bin/python -m rest_api_checker.sensitivity_execution --help

```text
usage: sensitivity_execution.py [-h] --candidate CANDIDATE --acceptance
                                ACCEPTANCE [--env-file ENV_FILE]
                                [--experiment-id EXPERIMENT_ID]
                                [--spool SPOOL]
                                [--technical-review TECHNICAL_REVIEW]
                                {prepare,run,reconcile}

Hash-accepted sensitivity adapter over the qualified sequential attempt
lifecycle.

positional arguments:
  {prepare,run,reconcile}

options:
  -h, --help            show this help message and exit
  --candidate CANDIDATE
  --acceptance ACCEPTANCE
  --env-file ENV_FILE
  --experiment-id EXPERIMENT_ID
  --spool SPOOL
  --technical-review TECHNICAL_REVIEW
```

## .venv/bin/python -m rest_api_checker.interface_pilot_v2 --help

```text
usage: interface_pilot_v2.py [-h] --cases
                             {DEV-01,DEV-02,DEV-03,DEV-04,DEV-05,DEV-06,DEV-07,DEV-08,DEV-09,DEV-10,DEV-11,DEV-12}
                             {DEV-01,DEV-02,DEV-03,DEV-04,DEV-05,DEV-06,DEV-07,DEV-08,DEV-09,DEV-10,DEV-11,DEV-12}
                             --model-digests MODEL_DIGESTS --output OUTPUT

Prepare exactly 18 development-only interface requests, without SQL or HTTP.

options:
  -h, --help            show this help message and exit
  --cases {DEV-01,DEV-02,DEV-03,DEV-04,DEV-05,DEV-06,DEV-07,DEV-08,DEV-09,DEV-10,DEV-11,DEV-12} {DEV-01,DEV-02,DEV-03,DEV-04,DEV-05,DEV-06,DEV-07,DEV-08,DEV-09,DEV-10,DEV-11,DEV-12}
  --model-digests MODEL_DIGESTS
                        JSON object mapping the three model names to full,
                        operator-verified digests
  --output OUTPUT       New directory; no existing files are overwritten
```

## .venv/bin/python -m rest_api_checker.interface_pilot_v2_live --help

```text
usage: interface_pilot_v2_live.py [-h] --prepared PREPARED --cases
                                  {DEV-01,DEV-02,DEV-03,DEV-04,DEV-05,DEV-06,DEV-07,DEV-08,DEV-09,DEV-10,DEV-11,DEV-12}
                                  {DEV-01,DEV-02,DEV-03,DEV-04,DEV-05,DEV-06,DEV-07,DEV-08,DEV-09,DEV-10,DEV-11,DEV-12}
                                  --model-digests MODEL_DIGESTS
                                  --runtime-binding RUNTIME_BINDING
                                  --context-proofs CONTEXT_PROOFS --output
                                  OUTPUT --confirm-development-interface-pilot
                                  {run}

Single-use dispatch of an exact, development-only 18-request interface pilot.

positional arguments:
  {run}

options:
  -h, --help            show this help message and exit
  --prepared PREPARED
  --cases {DEV-01,DEV-02,DEV-03,DEV-04,DEV-05,DEV-06,DEV-07,DEV-08,DEV-09,DEV-10,DEV-11,DEV-12} {DEV-01,DEV-02,DEV-03,DEV-04,DEV-05,DEV-06,DEV-07,DEV-08,DEV-09,DEV-10,DEV-11,DEV-12}
  --model-digests MODEL_DIGESTS
  --runtime-binding RUNTIME_BINDING
  --context-proofs CONTEXT_PROOFS
  --output OUTPUT
  --confirm-development-interface-pilot
```

## .venv/bin/python -m rest_api_checker.development_dataset --help

```text
usage: development_dataset.py [-h] --research-repository RESEARCH_REPOSITORY
                              [--output OUTPUT]

Materialize only the approved development_dataset_v1.md inventory.
Expectations are checked after construction's artifact-only Oracle calls.
Output is a candidate for manual review, never an automatically released
reference set.

options:
  -h, --help            show this help message and exit
  --research-repository RESEARCH_REPOSITORY
  --output OUTPUT
```

## .venv/bin/python -m rest_api_checker.main_v2_context --help

```text
usage: main_v2_context.py [-h] --release RELEASE --prepared PREPARED --output
                          OUTPUT [--root ROOT] [--research RESEARCH]
                          [--confirm-native-render-tokenize-only]

Separate native render/tokenize evidence preparation. Never requests
generation. Uses the already qualified Evaluation-v2 render-only path and
native tokenizer. This command is intentionally separate from the offline
materializer.

options:
  -h, --help            show this help message and exit
  --release RELEASE
  --prepared PREPARED
  --output OUTPUT
  --root ROOT
  --research RESEARCH
  --confirm-native-render-tokenize-only
```

## .venv/bin/python -m rest_api_checker.main_v2 --help

```text
usage: main_v2.py [-h] [--research RESEARCH]
                  {integrity,freeze-template,freeze,prepare,import-dataset,plan-template,materialize,execution-template,authorize-execution}
                  ...

Deterministic Main-v2 request preparation and SQL materialization; no
inference.

positional arguments:
  {integrity,freeze-template,freeze,prepare,import-dataset,plan-template,materialize,execution-template,authorize-execution}

options:
  -h, --help            show this help message and exit
  --research RESEARCH
```

## .venv/bin/python -m rest_api_checker.main_v2 integrity --help

```text
usage: main_v2.py integrity [-h] --archive ARCHIVE --review-dir REVIEW_DIR
                            --output OUTPUT

options:
  -h, --help            show this help message and exit
  --archive ARCHIVE
  --review-dir REVIEW_DIR
  --output OUTPUT
```

## .venv/bin/python -m rest_api_checker.main_v2 freeze --help

```text
usage: main_v2.py freeze [-h] --archive ARCHIVE --review-dir REVIEW_DIR
                         --output OUTPUT --integrity INTEGRITY --version
                         VERSION --approval APPROVAL

options:
  -h, --help            show this help message and exit
  --archive ARCHIVE
  --review-dir REVIEW_DIR
  --output OUTPUT
  --integrity INTEGRITY
  --version VERSION
  --approval APPROVAL
```

## .venv/bin/python -m rest_api_checker.main_v2 prepare --help

```text
usage: main_v2.py prepare [-h] --release RELEASE --output OUTPUT
                          [--runtime-qualification RUNTIME_QUALIFICATION]
                          [--runtime-manifest-sha256 RUNTIME_MANIFEST_SHA256]
                          [--runtime-receipt-sha256 RUNTIME_RECEIPT_SHA256]

options:
  -h, --help            show this help message and exit
  --release RELEASE
  --output OUTPUT
  --runtime-qualification RUNTIME_QUALIFICATION
  --runtime-manifest-sha256 RUNTIME_MANIFEST_SHA256
  --runtime-receipt-sha256 RUNTIME_RECEIPT_SHA256
```

## .venv/bin/python -m rest_api_checker.main_v2 materialize --help

```text
usage: main_v2.py materialize [-h] --release RELEASE --output OUTPUT
                              --env-file ENV_FILE --database DATABASE
                              --prepared PREPARED --context CONTEXT
                              --dataset-id DATASET_ID --authorization
                              AUTHORIZATION

options:
  -h, --help            show this help message and exit
  --release RELEASE
  --output OUTPUT
  --env-file ENV_FILE
  --database DATABASE
  --prepared PREPARED
  --context CONTEXT
  --dataset-id DATASET_ID
  --authorization AUTHORIZATION
```

## .venv/bin/python -m rest_api_checker.main_v2 execution-template --help

```text
usage: main_v2.py execution-template [-h] --env-file ENV_FILE --database
                                     DATABASE --dataset-id DATASET_ID
                                     --experiment-id EXPERIMENT_ID
                                     [--root ROOT] --output OUTPUT

options:
  -h, --help            show this help message and exit
  --env-file ENV_FILE
  --database DATABASE
  --dataset-id DATASET_ID
  --experiment-id EXPERIMENT_ID
  --root ROOT
  --output OUTPUT
```

## .venv/bin/python -m rest_api_checker.main_v2 authorize-execution --help

```text
usage: main_v2.py authorize-execution [-h] --env-file ENV_FILE --database
                                      DATABASE --dataset-id DATASET_ID
                                      --experiment-id EXPERIMENT_ID
                                      [--root ROOT] --output OUTPUT
                                      --authorization AUTHORIZATION

options:
  -h, --help            show this help message and exit
  --env-file ENV_FILE
  --database DATABASE
  --dataset-id DATASET_ID
  --experiment-id EXPERIMENT_ID
  --root ROOT
  --output OUTPUT
  --authorization AUTHORIZATION
```

## .venv/bin/python -m rest_api_checker.persistence --help

```text
usage: __main__.py [-h] --env-file ENV_FILE [--database DATABASE]
                   {init,create-test,destroy-test,migrate,version,backup,restore-test,import-dev,import-prompts}
                   ...

Explicit administrative/import CLI. No startup migration or model execution.

positional arguments:
  {init,create-test,destroy-test,migrate,version,backup,restore-test,import-dev,import-prompts}

options:
  -h, --help            show this help message and exit
  --env-file ENV_FILE
  --database DATABASE
```

## .venv/bin/python -m rest_api_checker.persistence --env-file /NONEXISTENT init --help

```text
usage: __main__.py init [-h]

options:
  -h, --help  show this help message and exit
```

## .venv/bin/python -m rest_api_checker.persistence --env-file /NONEXISTENT create-test --help

```text
usage: __main__.py create-test [-h]

options:
  -h, --help  show this help message and exit
```

## .venv/bin/python -m rest_api_checker.persistence --env-file /NONEXISTENT destroy-test --help

```text
usage: __main__.py destroy-test [-h]

options:
  -h, --help  show this help message and exit
```

## .venv/bin/python -m rest_api_checker.persistence --env-file /NONEXISTENT migrate --help

```text
usage: __main__.py migrate [-h] --expected-current EXPECTED_CURRENT

options:
  -h, --help            show this help message and exit
  --expected-current EXPECTED_CURRENT
```

## .venv/bin/python -m rest_api_checker.persistence --env-file /NONEXISTENT version --help

```text
usage: __main__.py version [-h]

options:
  -h, --help  show this help message and exit
```

## .venv/bin/python -m rest_api_checker.persistence --env-file /NONEXISTENT backup --help

```text
usage: __main__.py backup [-h] --server-path SERVER_PATH

options:
  -h, --help            show this help message and exit
  --server-path SERVER_PATH
```

## .venv/bin/python -m rest_api_checker.persistence --env-file /NONEXISTENT restore-test --help

```text
usage: __main__.py restore-test [-h] --server-path SERVER_PATH

options:
  -h, --help            show this help message and exit
  --server-path SERVER_PATH
```

## .venv/bin/python -m rest_api_checker.persistence --env-file /NONEXISTENT import-dev --help

```text
usage: __main__.py import-dev [-h] --staging STAGING --release RELEASE
                              --research RESEARCH

options:
  -h, --help           show this help message and exit
  --staging STAGING
  --release RELEASE
  --research RESEARCH
```

## .venv/bin/python -m rest_api_checker.persistence --env-file /NONEXISTENT import-prompts --help

```text
usage: __main__.py import-prompts [-h] --research RESEARCH

options:
  -h, --help           show this help message and exit
  --research RESEARCH
```

## .venv/bin/python -m rest_api_checker.main_v2 freeze-template --help

```text
usage: main_v2.py freeze-template [-h] --archive ARCHIVE --review-dir
                                  REVIEW_DIR --output OUTPUT --integrity
                                  INTEGRITY --version VERSION

options:
  -h, --help            show this help message and exit
  --archive ARCHIVE
  --review-dir REVIEW_DIR
  --output OUTPUT
  --integrity INTEGRITY
  --version VERSION
```

## .venv/bin/python -m rest_api_checker.main_v2 import-dataset --help

```text
usage: main_v2.py import-dataset [-h] --release RELEASE --output OUTPUT
                                 --env-file ENV_FILE --database DATABASE

options:
  -h, --help           show this help message and exit
  --release RELEASE
  --output OUTPUT
  --env-file ENV_FILE
  --database DATABASE
```

## .venv/bin/python -m rest_api_checker.main_v2 plan-template --help

```text
usage: main_v2.py plan-template [-h] --release RELEASE --output OUTPUT
                                --prepared PREPARED --context CONTEXT
                                --dataset-id DATASET_ID --database DATABASE

options:
  -h, --help            show this help message and exit
  --release RELEASE
  --output OUTPUT
  --prepared PREPARED
  --context CONTEXT
  --dataset-id DATASET_ID
  --database DATABASE
```

## .venv/bin/python tools/runtime_qualification/capture.py --help

```text
usage: capture.py [-h] {before,after}

positional arguments:
  {before,after}

options:
  -h, --help      show this help message and exit
```

## .venv/bin/python tools/final_evaluation_bases/prepare.py --help

```text
usage: prepare.py [-h] --research RESEARCH --output OUTPUT --technical-commit
                  TECHNICAL_COMMIT --materialized-at MATERIALIZED_AT

Serialize only the six bases of the hash-bound final construction plan. No
application imports, reference determination, child transformations or release
decisions. Invoke directly, never through the application package.

options:
  -h, --help            show this help message and exit
  --research RESEARCH
  --output OUTPUT
  --technical-commit TECHNICAL_COMMIT
  --materialized-at MATERIALIZED_AT
```

## .venv/bin/python tools/final_evaluation_candidates/prepare.py --help

```text
usage: prepare.py [-h] --research RESEARCH --technical TECHNICAL --output
                  OUTPUT --materialized-at MATERIALIZED_AT

Offline, pre-reference materialization of the exact author-confirmed plan.
Standalone standard library only. Never import the application, Oracle, schema
validators, providers or database. The caller must supply explicit
authorization.

options:
  -h, --help            show this help message and exit
  --research RESEARCH
  --technical TECHNICAL
  --output OUTPUT
  --materialized-at MATERIALIZED_AT
```

## .venv/bin/python tools/sqlserver_environment/probe.py --help

```text
usage: probe.py [-h] --env-file ENV_FILE --evidence EVIDENCE
                {initialize,verify,unique,backup,restore}

Disposable SQL Server compatibility probe. Never reads study artifacts. Run
each phase explicitly; failures preserve evidence and stop the phase. No
cleanup, application tables, migrations, Oracle imports, or provider calls.

positional arguments:
  {initialize,verify,unique,backup,restore}

options:
  -h, --help            show this help message and exit
  --env-file ENV_FILE
  --evidence EVIDENCE
```
