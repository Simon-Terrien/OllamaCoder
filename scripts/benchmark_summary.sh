#!/usr/bin/env bash
set -euo pipefail

file=${1:-logs/benchmark_results.jsonl}

if [[ ! -f "$file" ]]; then
  echo "Benchmark file not found: $file" >&2
  exit 1
fi

jq -s '
  def median(arr):
    if (arr|length) == 0 then 0
    elif (arr|length) % 2 == 1 then arr[(arr|length-1)/2]
    else (arr[(arr|length/2)-1] + arr[(arr|length/2)]) / 2
    end;
  . as $all |
  {
    count: ($all|length),
    successes: ($all|map(select(.validator_ok==true))|length),
    success_rate: (if ($all|length)==0 then 0 else ( $all|map(select(.validator_ok==true))|length ) / ($all|length) end),
    avg_duration_sec: (if ($all|length)==0 then 0 else ($all|map(.duration_sec)|add) / ($all|length) end),
    median_duration_sec: (median($all|map(.duration_sec)|sort)),
    avg_loops: (if ($all|length)==0 then 0 else ($all|map(.loop_count)|add) / ($all|length) end),
    blocked: ($all|map(select(.blocked==true))|length)
  }
' "$file"
