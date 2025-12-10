# Running Batch Jobs

## Overview
This documentation provides guidance on how to run batch jobs efficiently and effectively.

## Steps to Run a Batch Job
1. **Prepare the Environment**
   - Ensure that all necessary dependencies are installed.
   - Set up any required configuration files.

2. **Write the Script**
   - Create a script file (e.g., `batch_job.sh`) containing the commands to be executed.
   - Make sure the script is executable by running: `chmod +x batch_job.sh`

3. **Submit the Job**
   - Use the appropriate command to submit the job. For example, on a cluster system, use `qsub batch_job.sh`.

4. **Monitor and Manage Jobs**
   - Monitor the progress of your job using commands like `qstat` or equivalent.
   - If necessary, cancel jobs using `qdel <job_id>`.

## Best Practices
- **Resource Allocation**
  - Allocate resources appropriately to avoid overloading the system.
- **Error Handling**
  - Implement error handling in your script to manage failures gracefully.
- **Logging**
  - Redirect output and errors to log files for later review.

## Example Script
```bash
#!/bin/bash
# batch_job.sh

echo "Starting batch job at $(date)"

# Your commands here

echo "Batch job completed at $(date)"
```

## Benchmarks

- Run sample tasks through the agent and log metrics:
  `uv run python scripts/benchmark.py --coder-model qwen2.5-coder:7b --reviewer-model llama3.2`
- Summarize accumulated runs (JSONL):
  `scripts/benchmark_summary.sh logs/benchmark_results.jsonl`
