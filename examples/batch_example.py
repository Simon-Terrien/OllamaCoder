"""Example script demonstrating batch processing capabilities."""

import time
from pathlib import Path

import requests


def example_1_batch_agent_tasks():
    """Example 1: Process multiple coding tasks in batch."""
    print("\n" + "=" * 60)
    print("Example 1: Batch Agent Tasks")
    print("=" * 60)

    # Define tasks
    tasks = [
        {
            "id": "task1",
            "description": "Create a Python function to calculate fibonacci numbers",
        },
        {"id": "task2", "description": "Add error handling to the fibonacci function"},
        {"id": "task3", "description": "Write unit tests for the fibonacci function"},
        {"id": "task4", "description": "Add docstrings to the fibonacci function"},
        {
            "id": "task5",
            "description": "Optimize the fibonacci function for large numbers",
        },
    ]

    # Submit batch job
    response = requests.post(
        "http://127.0.0.1:8000/batch/agent-tasks",
        json={
            "tasks": tasks,
            "chunk_size": 2,
            "parallel": 2,
            "max_loops": 10,
        },
    )

    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return

    job = response.json()
    job_id = job["job_id"]

    print(f"✅ Job submitted: {job_id}")
    print(f"📊 Total tasks: {len(tasks)}")
    print("\nMonitoring progress...")

    # Poll for completion
    while True:
        response = requests.get(f"http://127.0.0.1:8000/batch/jobs/{job_id}")
        job = response.json()

        status = job["status"]
        progress = job.get("progress", 0)

        # Show progress
        metadata = job.get("metadata", {})
        prog_data = metadata.get("progress", {})

        if prog_data:
            print(
                f"\r📈 Progress: {progress:.1f}% | "
                f"✓ {prog_data.get('successful', 0)} | "
                f"✗ {prog_data.get('failed', 0)} | "
                f"⚡ {prog_data.get('items_per_second', 0):.2f} tasks/s",
                end="",
            )

        if status in ["completed", "failed", "cancelled"]:
            print()
            break

        time.sleep(2)

    # Print results
    print(f"\n{'=' * 60}")
    if status == "completed":
        result = job["result"]
        summary = result["summary"]
        print("✅ Batch completed successfully!")
        print(f"   Total: {summary['total']}")
        print(f"   Successful: {summary['successful']}")
        print(f"   Failed: {summary['failed']}")
        print(f"   Elapsed: {result['elapsed_seconds']:.1f}s")
    else:
        print(f"❌ Job {status}")
        if job.get("error"):
            print(f"   Error: {job['error']}")


def example_2_batch_validation():
    """Example 2: Validate multiple files in batch."""
    print("\n" + "=" * 60)
    print("Example 2: Batch Validation")
    print("=" * 60)

    # Find Python files
    src_path = Path("src/ollama_coder/core")
    python_files = list(src_path.glob("*.py"))

    if not python_files:
        print("No Python files found in src/ollama_coder/core")
        return

    targets = [
        {"id": str(f.name), "path": str(f)}
        for f in python_files[:5]  # Limit to 5 files for demo
    ]

    print(f"Validating {len(targets)} files...")

    # Submit validation job
    response = requests.post(
        "http://127.0.0.1:8000/batch/validation",
        json={
            "targets": targets,
            "check_command": "python -m py_compile",  # Simple syntax check
            "parallel": 3,
        },
    )

    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return

    job = response.json()
    job_id = job["job_id"]

    # Wait for completion
    while True:
        response = requests.get(f"http://127.0.0.1:8000/batch/jobs/{job_id}")
        job = response.json()

        if job["status"] in ["completed", "failed", "cancelled"]:
            break

        time.sleep(1)

    # Print results
    if job["status"] == "completed":
        result = job["result"]
        summary = result["summary"]
        print("✅ Validation completed!")
        print(f"   Passed: {summary['successful']}")
        print(f"   Failed: {summary['failed']}")

        # Show failed files
        if summary["failed"] > 0:
            print("\n   Failed files:")
            for r in result["results"]:
                if r["status"] == "failed":
                    print(f"     - {r['path']}: {r.get('error', 'Unknown error')}")


def example_3_batch_tests():
    """Example 3: Run multiple test modules in batch."""
    print("\n" + "=" * 60)
    print("Example 3: Batch Test Execution")
    print("=" * 60)

    # Find test files
    test_path = Path("tests")
    test_files = list(test_path.glob("test_*.py"))

    if not test_files:
        print("No test files found")
        return

    modules = [{"id": f.stem, "path": str(f)} for f in test_files]

    print(f"Running {len(modules)} test modules...")

    # Submit test job
    response = requests.post(
        "http://127.0.0.1:8000/batch/tests",
        json={"modules": modules, "test_command": "pytest -q", "parallel": 3},
    )

    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return

    job = response.json()
    job_id = job["job_id"]

    # Wait for completion
    while True:
        response = requests.get(f"http://127.0.0.1:8000/batch/jobs/{job_id}")
        job = response.json()

        if job["status"] in ["completed", "failed", "cancelled"]:
            break

        print(f"\r📊 Progress: {job.get('progress', 0):.1f}%", end="")
        time.sleep(1)

    print()

    # Print results
    if job["status"] == "completed":
        result = job["result"]
        summary = result["summary"]
        print("✅ Tests completed!")
        print(f"   Passed: {summary['passed']}")
        print(f"   Failed: {summary['failed']}")
        print(f"   Time: {result['elapsed_seconds']:.1f}s")


def example_4_batch_mcp_operations():
    """Example 4: Perform bulk MCP operations."""
    print("\n" + "=" * 60)
    print("Example 4: Batch MCP Operations")
    print("=" * 60)

    # Define operations
    operations = [
        {"type": "read", "path": "README.md"},
        {"type": "list", "path": "src/"},
        {"type": "list", "path": "tests/"},
        {"type": "command", "command": "echo 'Batch MCP test'"},
    ]

    print(f"Executing {len(operations)} MCP operations...")

    # Submit MCP job
    response = requests.post(
        "http://127.0.0.1:8000/batch/mcp-operations",
        json={"operations": operations, "parallel": 2},
    )

    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return

    job = response.json()
    job_id = job["job_id"]

    # Wait for completion
    while True:
        response = requests.get(f"http://127.0.0.1:8000/batch/jobs/{job_id}")
        job = response.json()

        if job["status"] in ["completed", "failed", "cancelled"]:
            break

        time.sleep(0.5)

    # Print results
    if job["status"] == "completed":
        result = job["result"]
        summary = result["summary"]
        print("✅ Operations completed!")
        print(f"   Successful: {summary['successful']}")
        print(f"   Failed: {summary['failed']}")


def example_5_queue_stats():
    """Example 5: Get queue statistics."""
    print("\n" + "=" * 60)
    print("Example 5: Queue Statistics")
    print("=" * 60)

    response = requests.get("http://127.0.0.1:8000/batch/stats")

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return

    stats = response.json()["stats"]

    print("Queue Statistics:")
    print(f"  Total jobs: {stats.get('total', 0)}")
    print(f"  Queued: {stats.get('queued', 0)}")
    print(f"  Running: {stats.get('running', 0)}")
    print(f"  Completed: {stats.get('completed', 0)}")
    print(f"  Failed: {stats.get('failed', 0)}")
    print(f"  Cancelled: {stats.get('cancelled', 0)}")


def main():
    """Run all examples."""
    print("=" * 60)
    print("Ollama Coder - Batch Processing Examples")
    print("=" * 60)
    print("\nMake sure the API server is running:")
    print("  uv run python -m ollama_coder.api")
    print()

    # Check if API is running
    try:
        response = requests.get("http://127.0.0.1:8000/health", timeout=2)
        if response.status_code != 200:
            print("❌ API server is not responding. Please start it first.")
            return
    except Exception as e:
        print(f"❌ Cannot connect to API server: {e}")
        print("   Please start it with: uv run python -m ollama_coder.api")
        return

    print("✅ API server is running\n")

    # Run examples
    try:
        # Example 5: Queue stats (quick)
        example_5_queue_stats()

        # Example 4: MCP operations (quick)
        example_4_batch_mcp_operations()

        # Example 2: Validation (moderate)
        example_2_batch_validation()

        # Example 3: Tests (moderate)
        example_3_batch_tests()

        # Example 1: Agent tasks (slow - uncomment to run)
        # example_1_batch_agent_tasks()

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
