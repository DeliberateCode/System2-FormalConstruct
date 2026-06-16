# Benchmarking Changelog

## 2026-06-15: Real-time Logging

### Changes
- **Incremental result saving**: Individual problem results are now saved immediately upon completion to `results/run_*/problems/{problem_id}/`
- **Live progress output**: Progress messages now flush immediately with `flush=True`
- **Early directory creation**: Run directory is created at benchmark start and displayed to user
- **Max turns configurable**: Added `--max-turns` CLI parameter (default: 100, up from 50)

### Benefits
- Monitor benchmark progress in real-time by checking the results directory
- No need to wait for full batch completion to see intermediate results
- Can inspect individual problem outputs while benchmark is still running

### Usage
```bash
# Start benchmark
python -m benchmarking run --sample 10 --timeout 600 --max-turns 100

# In another terminal, monitor live results
watch -n 5 'ls -la benchmarking/results/run_*/problems/ | tail -20'

# Check a specific problem as it completes
cat benchmarking/results/run_*/problems/lean_workbook_plus_8048/result.json
```

### Implementation Details
- `run_batch()` accepts optional `live_save_dir` parameter
- New `_save_single_result()` function writes individual results
- `save_run()` now only writes final metadata (results already saved)
- Progress callback includes `flush=True` for immediate stdout output
