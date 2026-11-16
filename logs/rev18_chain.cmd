@echo off
cd /d C:\coding\Argus-pilot50
for %%A in (R F P) do python -X utf8 scripts/run_loop_f.py --arm %%A --rep 1 --model gemini31 gemini35 --workers 2 --cap-usd 2 >> logs/rev18_rep1_%%A.log 2>&1
for %%A in (F P) do python -X utf8 scripts/run_loop_f.py --arm %%A --temp 0 --model gemini31 gemini35 --workers 2 --cap-usd 1.5 >> logs/rev18_t0_%%A.log 2>&1
for %%A in (R F P) do python -X utf8 scripts/run_loop_f.py --arm %%A --rep 2 --model gemini31 gemini35 --workers 2 --cap-usd 2 >> logs/rev18_rep2_%%A.log 2>&1
