#!/usr/bin/env bash
# Generate LLM-spec fixtures via NVIDIA NIM and/or Groq.
#
# Saves three artefacts per call:
#   benchmark/<task>/responses/<alias>.json    full API response, latency, usage,
#                                              reasoning trace (when available)
#   benchmark/<task>/responses/<alias>.txt     reasoning / chain-of-thought trace
#                                              (separate file for readability)
#   benchmark/<task>/fixtures/<alias>.py       the extracted Python spec
#
# Models supported (set the matching API key in .env to enable):
#   qwen        NVIDIA NIM       qwen/qwen3-coder-480b-a35b-instruct
#   llama       NVIDIA NIM       meta/llama-3.3-70b-instruct
#   gpt-oss     Groq             openai/gpt-oss-120b  (reasoning_effort=medium)
#   compound    Groq             groq/compound  (tools: web_search, code_interpreter)
#
# Each (task, model) is written atomically: a temp file is staged then renamed,
# so partial progress survives a Ctrl-C or rate-limit kill.
#
# Usage:
#   bash scripts/gen_fixtures.sh                      # all tasks, all available models
#   bash scripts/gen_fixtures.sh --task 06_token      # one task
#   bash scripts/gen_fixtures.sh --model qwen         # one model
#   bash scripts/gen_fixtures.sh --task 11_brd --model gpt-oss

set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO/.env"
if [ ! -f "$ENV_FILE" ]; then
  ENV_FILE="$REPO/../.env"
fi
if [ -f "$ENV_FILE" ]; then
  set -a; . "$ENV_FILE"; set +a
fi

# ---------------------------------------------------------------- model table
# alias -> "provider|model-id"
declare -A MODELS=(
  [qwen]="nim|qwen/qwen3-coder-480b-a35b-instruct"
  [llama]="nim|meta/llama-3.3-70b-instruct"
  [gpt-oss]="groq|openai/gpt-oss-120b"
  [compound]="groq|groq/compound"
)

PROMPT_HEADER=$'You are a formal-methods expert. Given a natural-language requirement,\nemit a formal specification as two Python functions named exactly `pre`\nand `post`.\n\n  * `pre(i)` returns True if and only if `i` is a valid input.\n  * `post(i, o)` returns True if and only if `o` is a correct output for\n    valid input `i`.\n\nOutput ONLY executable Python source code defining `pre` and `post` at\nthe top level. No markdown fences, no commentary, no imports outside\nthe Python standard library.\n\nRequirement:\n'

# --------------------------------------------------------------- helper: call one
# Args: provider model prompt response_json_out spec_py_out reasoning_out
call_one () {
  local provider="$1" model="$2" prompt="$3" rsp_out="$4" spec_out="$5" reason_out="$6"
  local url payload key headers_args extra_args

  case "$provider" in
    nim)
      url="https://integrate.api.nvidia.com/v1/chat/completions"
      key="${NVIDIA_API_KEY:-}"
      extra_args='{"temperature":0.0,"max_tokens":2048}'
      ;;
    groq)
      url="https://api.groq.com/openai/v1/chat/completions"
      key="${GROQ_API_KEY:-}"
      # Groq reasoning models need `reasoning_effort`; compound needs tools.
      if [ "$model" = "openai/gpt-oss-120b" ]; then
        extra_args='{"temperature":0.0,"max_completion_tokens":8192,"reasoning_effort":"medium"}'
      elif [ "$model" = "groq/compound" ]; then
        extra_args='{"temperature":0.0,"max_completion_tokens":2048,"compound_custom":{"tools":{"enabled_tools":["code_interpreter"]}}}'
      else
        extra_args='{"temperature":0.0,"max_completion_tokens":2048}'
      fi
      ;;
    *)
      echo " unknown-provider"; return 1 ;;
  esac

  if [ -z "$key" ]; then
    echo " no-key($provider)"
    return 2
  fi

  # Build request body (Python for safe JSON escaping)
  payload=$(python -c "
import json, sys
extra = json.loads(sys.argv[3])
body = {'model': sys.argv[1],
        'messages':[{'role':'user','content': sys.argv[2]}]}
body.update(extra)
print(json.dumps(body))
" "$model" "$prompt" "$extra_args")

  local t0 t1 elapsed
  t0=$(date +%s)
  local raw
  if ! raw=$(curl -sS --max-time 180 \
      -H "Authorization: Bearer $key" \
      -H "Content-Type: application/json" \
      -X POST "$url" \
      -d "$payload"); then
    echo " curl-failed"
    return 1
  fi
  t1=$(date +%s)
  elapsed=$((t1 - t0))

  # Extract spec + reasoning, then write all three artefacts atomically.
  python -c "
import json, os, re, sys, time

data = json.loads(sys.stdin.read())
provider, model, elapsed = sys.argv[1], sys.argv[2], int(sys.argv[3])
rsp_out, spec_out, reason_out = sys.argv[4], sys.argv[5], sys.argv[6]

content = ''
reasoning = ''
extract_status = 'ok'
usage = {}

if 'choices' in data and data['choices']:
    msg = data['choices'][0].get('message', {})
    content = msg.get('content') or ''
    # Different providers stash reasoning under different keys.
    reasoning = (
        msg.get('reasoning')
        or msg.get('reasoning_content')
        or (msg.get('executed_tools') and json.dumps(msg['executed_tools'], indent=2))
        or ''
    )
    usage = data.get('usage', {}) or {}
else:
    extract_status = 'no_choices'

# Strip markdown fences if present
src = content.strip()
if src.startswith('\`\`\`'):
    lines = src.splitlines()
    if len(lines) >= 2 and lines[-1].strip().startswith('\`\`\`'):
        src = '\n'.join(lines[1:-1])

# AST sanity check (does NOT block writing — we want the failure recorded)
import ast
try:
    ast.parse(src)
    if 'def pre' not in src or 'def post' not in src:
        extract_status = 'missing_pre_or_post'
except SyntaxError as e:
    extract_status = f'syntax_error:{e.msg}'

# Atomic write helper
def atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, path)

# 1. Full response JSON with metadata
meta = {
    'provider': provider,
    'model': model,
    'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'elapsed_seconds': elapsed,
    'extract_status': extract_status,
    'usage': usage,
    'reasoning_chars': len(reasoning),
    'content_chars': len(content),
    'response': data,
}
atomic_write(rsp_out, json.dumps(meta, indent=2, ensure_ascii=False))

# 2. Reasoning trace (CoT) as separate readable file
if reasoning:
    atomic_write(reason_out, reasoning + '\n')

# 3. Extracted spec
header = (
    f'# Generated by DiffSpec-PBT live mode\n'
    f'# provider: {provider}\n'
    f'# model: {model}\n'
    f'# timestamp_utc: {meta[\"timestamp_utc\"]}\n'
    f'# extract_status: {extract_status}\n'
    f'# elapsed_seconds: {elapsed}\n'
)
atomic_write(spec_out, header + src + '\n')

print(f' ok status={extract_status} content={len(content)}ch reasoning={len(reasoning)}ch t={elapsed}s')
" "$provider" "$model" "$elapsed" "$rsp_out" "$spec_out" "$reason_out" <<<"$raw"
}

# --------------------------------------------------------------- arg parsing
TASK_FILTER=""
MODEL_FILTER=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --task)  TASK_FILTER="$2"; shift 2 ;;
    --model) MODEL_FILTER="$2"; shift 2 ;;
    *)       echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Skip aliases whose backend has no key
AVAILABLE=()
for alias in "${!MODELS[@]}"; do
  IFS='|' read -r provider model <<< "${MODELS[$alias]}"
  case "$provider" in
    nim)  [ -n "${NVIDIA_API_KEY:-}" ] && AVAILABLE+=("$alias") ;;
    groq) [ -n "${GROQ_API_KEY:-}" ]   && AVAILABLE+=("$alias") ;;
  esac
done

if [ -n "$MODEL_FILTER" ]; then
  AVAILABLE=("$MODEL_FILTER")
fi

if [ "${#AVAILABLE[@]}" -eq 0 ]; then
  echo "no models available (set NVIDIA_API_KEY and/or GROQ_API_KEY in .env)" >&2
  exit 2
fi

echo "Available models: ${AVAILABLE[*]}"

# --------------------------------------------------------------- main loop
for task_dir in "$REPO"/benchmark/*/; do
  task=$(basename "$task_dir")
  [ "$task" = "__pycache__" ] && continue
  [ ! -f "$task_dir/requirement.md" ] && continue
  if [ -n "$TASK_FILTER" ] && [[ "$task" != *"$TASK_FILTER"* ]]; then
    continue
  fi
  echo "[$(date +%H:%M:%S)] $task"
  prompt="${PROMPT_HEADER}$(cat "$task_dir/requirement.md")"
  mkdir -p "$task_dir/fixtures" "$task_dir/responses"

  for alias in "${AVAILABLE[@]}"; do
    IFS='|' read -r provider model <<< "${MODELS[$alias]}"
    rsp_out="$task_dir/responses/${alias}.json"
    spec_out="$task_dir/fixtures/${alias}.py"
    reason_out="$task_dir/responses/${alias}.reasoning.txt"
    echo -n "  $alias ($provider/$model) ..."
    if call_one "$provider" "$model" "$prompt" "$rsp_out" "$spec_out" "$reason_out"; then
      :
    else
      echo "    -> FAILED"
    fi
  done
done
echo "Done."
