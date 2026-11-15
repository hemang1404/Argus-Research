#!/bin/bash
# waits for the 120B pass of Revision 19 to end, then runs the 20B pass with Gemma on the 45 tasks skipped earlier (same image pulls)
cd /c/coding/Argus-pilot50
alive() { powershell -NoProfile -Command "if (Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match 'run_loop4' -and \$_.Name -match '^python' }) { exit 0 } else { exit 1 }"; }
while alive; do sleep 60; done
echo "$(date +%H:%M) 120B pass ended: $(wc -l < data/loop4/trajectories.jsonl) tasks; starting 20B pass with --gemma --gemma-fill" >> logs/after_120b.log
python -X utf8 scripts/run_loop4.py --model openai/gpt-oss-20b --out-dir data/loop4_20b --workers 3 --gemma --gemma-fill >> logs/rev19.log 2>&1
echo "$(date +%H:%M) 20B pass ended" >> logs/after_120b.log
