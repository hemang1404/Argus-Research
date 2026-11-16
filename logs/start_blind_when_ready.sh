cd /c/coding/Argus-pilot50
until grep -q "grading complete" logs/grade_new_runs.log; do sleep 60; done
echo "docker free, starting blind run: $(date)" > logs/blind_started.txt
python -X utf8 scripts/run_blind.py --workers 3 > logs/blind.log 2>&1
echo "blind run finished: $(date)" >> logs/blind_started.txt
