cd /c/coding/Argus-pilot50
python -X utf8 scripts/run_loop2.py --model openai/gpt-oss-20b --out-dir data/loop2_20b --workers 3 > logs/loop2_20b.log 2>&1
mkdir -p data/loop3_20b && cp data/loop2_20b/calls.jsonl data/loop3_20b/calls.jsonl
python -X utf8 scripts/run_loop3.py --model openai/gpt-oss-20b --out-dir data/loop3_20b --workers 2 > logs/loop3_20b.log 2>&1
echo chain-done > logs/chain_20b_done.txt
