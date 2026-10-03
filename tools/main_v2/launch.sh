#!/bin/bash
# One explicitly selected persisted Main-v2 experiment. No retry loop.
set -euo pipefail
if [[ $# -lt 5 || $# -gt 6 ]]; then
  echo 'Usage: launch.sh ENV_FILE DATABASE DATASET_ID EXPERIMENT_ID DURABLE_RUN_DIR [--resume]' >&2
  exit 2
fi
task_root="$(cd "$(dirname "$0")/../.." && pwd -P)"
env_file="$1"
database="$2"
dataset_id="$3"
experiment_id="$4"
run_dir="$5"
resume=false
if [[ $# == 6 ]]; then
  [[ "$6" == --resume ]] || exit 2
  resume=true
fi
[[ "$dataset_id" =~ ^[1-9][0-9]*$ && "$experiment_id" =~ ^[1-9][0-9]*$ ]] || exit 2
[[ "$run_dir" == /* && -f "$env_file" ]] || exit 2
mkdir -p "$run_dir"
run_dir="$(cd "$run_dir" && pwd -P)"
case "$run_dir" in
  /tmp|/tmp/*|/private/tmp|/private/tmp/*|/var/folders/*|/private/var/folders/*)
    echo 'Use a durable run directory outside temporary storage.' >&2; exit 2 ;;
esac
minimum_kib="${MAIN_V2_MIN_FREE_KIB:-5242880}"
[[ "$minimum_kib" =~ ^[1-9][0-9]*$ ]] || exit 2
available_kib="$(df -Pk "$run_dir" | awk 'END {print $4}')"
[[ "$available_kib" -ge "$minimum_kib" ]] || { echo 'Insufficient free disk for the configured operational reserve.' >&2; exit 3; }
invocation="$run_dir/launch-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir "$invocation"
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/openssl@3/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
cli=("$task_root/.venv/bin/rest-api-checker" --root "$task_root" --env-file "$env_file" --database "$database")
echo "Started $(date -u); logs and receipts: $invocation; spool: $run_dir/spool; free KiB: $available_kib"
# The full dry-run includes real SQL health/schema/source closure and metadata-only
# Ollama health/version/model identity. It makes no generation calls.
"${cli[@]}" experiment batch-status "$experiment_id" --dataset-id "$dataset_id" --json > "$invocation/status-before.json" 2> "$invocation/preflight.stderr.log"
"${cli[@]}" experiment run-batch "$experiment_id" --dataset-id "$dataset_id" --dry-run --json > "$invocation/dry-run.json" 2>> "$invocation/preflight.stderr.log"
"$task_root/.venv/bin/python" - "$invocation/dry-run.json" <<'PY'
import json, sys
from rest_api_checker.experiment.request import MODELS, SEEDS, OPTIONS
from rest_api_checker.persistence.importer import PROMPT_HASHES
p = json.load(open(sys.argv[1]))['plan']
assert p['problematic'] == 0 and p['planned'] == p['cases'] * len(MODELS) * len(SEEDS)
assert [m['name'] for m in p['models']] == list(MODELS) and p['seeds'] == list(SEEDS.values())
assert p['repetitions'] == len(SEEDS) and p['output_mode'] == 'format_json'
assert p['prompt_sha256'] == PROMPT_HASHES['P2'] and p['token_limit'] == OPTIONS['num_predict']
print(json.dumps({k: p[k] for k in ('dataset', 'experiment_id', 'cases', 'models', 'repetitions', 'seeds',
    'planned', 'prompt', 'prompt_sha256', 'output_mode', 'token_limit', 'runtime', 'setup_sha256', 'problematic')}, indent=2))
PY
echo "Main begins $(date -u); no automatic retry."
code=0
run_command=("${cli[@]}" experiment run-batch "$experiment_id" --dataset-id "$dataset_id" --spool "$run_dir/spool" --yes --json)
if [[ "$resume" == true ]]; then
  run_command+=(--resume)
fi
/usr/bin/caffeinate -i -s "${run_command[@]}" > "$invocation/main-receipt.json" 2> "$invocation/main.stderr.log" || code=$?
printf 'Main exit code: %s; ended %s\n' "$code" "$(date -u)" | tee "$invocation/exit.txt"
"${cli[@]}" experiment batch-status "$experiment_id" --dataset-id "$dataset_id" --json > "$invocation/status-after.json" 2> "$invocation/status-after.stderr.log" || true
exit "$code"
