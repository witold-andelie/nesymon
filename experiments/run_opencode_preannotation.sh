#!/bin/bash
# Pre-annotate one trajectory per opencode call, in parallel, with retries.
# Usage: run_opencode_preannotation.sh WORK_DIR MODEL PARALLEL [NAME ...]
# WORK_DIR holds INSTRUCTIONS.md, claude/ examples, in/NAME.txt; results go to out/NAME.json.
# The work dir should sit outside the repository so the agent cannot read human labels.
set -u
W=$1; MODEL=$2; PAR=$3; shift 3
one() {
  name=$1
  for attempt in 1 2 3; do
    [ -s "$W/out/$name.json" ] && python3 -I -c "import json,sys; d=json.load(open(sys.argv[1])); assert isinstance(d, dict) and d" "$W/out/$name.json" 2>/dev/null && return 0
    rm -f "$W/out/$name.json"
    (cd "$W" && opencode run -m "$MODEL" --auto --archived --title "preannotate $name" \
      "Read INSTRUCTIONS.md in this directory and carry out the task for the single input file in/$name.txt only. Do not read any file outside this directory. Write out/$name.json and nothing else.") \
      > "$W/logs/$name.$attempt.log" 2>&1
  done
  echo "FAILED $name" >> "$W/failed.txt"
}
export -f one; export W MODEL
mkdir -p "$W/out" "$W/logs"
if [ $# -gt 0 ]; then printf '%s\n' "$@"; else ls "$W/in" | sed 's/\.txt$//'; fi | xargs -P "$PAR" -I{} bash -c 'one "$@"' _ {}
echo "done: $(ls "$W/out" | wc -l) outputs, $(cat "$W/failed.txt" 2>/dev/null | wc -l) failures"
