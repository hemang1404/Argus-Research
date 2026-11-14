#!/bin/bash
# Waits for the blind run to finish (restarting it, up to 3 times, if tasks are missing, e.g. failed pulls),
# then starts the Revision 18 batch (one image pull per task for all remaining arm specs). Logs to logs/after_blind.log
cd /c/coding/Argus-pilot50
alive() { powershell -NoProfile -Command "if (Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match 'run_blind.py' -and \$_.Name -match 'python' }) { exit 0 } else { exit 1 }"; }
count() { python -X utf8 -c "import json;print(len({json.loads(l)['iid'] for l in open('data/blind/trajectories.jsonl',encoding='utf8')}))"; }
for round in 0 1 2 3; do
  while alive; do sleep 120; done
  n=$(count); echo "$(date +%H:%M) blind process ended; tasks recorded: $n" >> logs/after_blind.log
  if [ "$n" -ge 200 ]; then break; fi
  if [ "$round" -lt 3 ]; then
    echo "$(date +%H:%M) restarting blind (round $((round+1)))" >> logs/after_blind.log
    powershell -NoProfile -Command "Start-Process -FilePath cmd.exe -ArgumentList '/c python -X utf8 scripts/run_blind.py --workers 3 >> logs/blind.log 2>&1' -WorkingDirectory C:\coding\Argus-pilot50 -WindowStyle Hidden"
    sleep 60
  fi
done
echo "$(date +%H:%M) blind finished with $(count) tasks; starting Revision 18 batch" >> logs/after_blind.log
powershell -NoProfile -Command "Start-Process -FilePath cmd.exe -ArgumentList '/c python -X utf8 scripts/run_loop_f.py --specs R:1:1 F:1:1 P:1:1 F:0:0 P:0:0 R:2:1 F:2:1 P:2:1 --model gemini31 gemini35 --workers 2 --cap-usd 5.5 >> logs/rev18_batch.log 2>&1' -WorkingDirectory C:\coding\Argus-pilot50 -WindowStyle Hidden"
echo "$(date +%H:%M) Revision 18 batch launched" >> logs/after_blind.log
