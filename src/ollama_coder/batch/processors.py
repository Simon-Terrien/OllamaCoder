"""Batch processors for different operation types."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import RunConfig
from ..core.supervisor import build_graph
from ..core.mcp_loader import get_mcp_tools
from .job_queue import Job, JobQueue
from .progress import ProgressTracker


class BatchAgentProcessor:
    """Process multiple coding tasks through the agent system in parallel."""

    def __init__(self, config: Optional[RunConfig] = None):
        """Initialize batch agent processor.

        Args:
            config: Agent configuration (uses defaults if None)
        """
        self.config = config or RunConfig()

    async def process(self, job: Job, queue: JobQueue) -> Dict[str, Any]:
        """Process batch agent tasks.

        Job data format:
        {
            "tasks": [
                {"id": "task1", "description": "Create hello.py"},
                {"id": "task2", "description": "Add tests"}
            ],
            "chunk_size": 10,  # Optional: tasks per chunk
            "parallel": 3,     # Optional: parallel executions
        }

        Args:
            job: Job to process
            queue: Job queue instance

        Returns:
            Processing results
        """
        tasks = job.data.get("tasks", [])
        chunk_size = job.data.get("chunk_size", 10)
        parallel = min(job.data.get("parallel", 3), 10)  # Max 10 parallel

        if not tasks:
            return {"error": "No tasks provided"}

        tracker = ProgressTracker(total=len(tasks))
        results = []

        # Build graph once
        graph = await build_graph(self.config)

        # Process tasks in chunks
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i : i + chunk_size]

            # Process chunk in parallel (limited concurrency)
            semaphore = asyncio.Semaphore(parallel)
            chunk_tasks = []

            for task_data in chunk:
                chunk_tasks.append(
                    self._process_single_task(
                        graph, task_data, tracker, semaphore
                    )
                )

            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)

            for task_data, result in zip(chunk, chunk_results):
                if isinstance(result, Exception):
                    results.append(
                        {
                            "task_id": task_data.get("id", "unknown"),
                            "status": "failed",
                            "error": str(result),
                        }
                    )
                else:
                    results.append(result)

            # Update job progress
            job.progress = tracker.percentage
            job.metadata["progress"] = tracker.to_dict()
            await queue.update_job(job)

        return {
            "summary": {
                "total": tracker.total,
                "successful": tracker.successful,
                "failed": tracker.failed,
                "skipped": tracker.skipped,
            },
            "results": results,
            "elapsed_seconds": tracker.elapsed_seconds,
        }

    async def _process_single_task(
        self,
        graph,
        task_data: Dict[str, Any],
        tracker: ProgressTracker,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Any]:
        """Process a single agent task.

        Args:
            graph: Compiled agent graph
            task_data: Task data with 'id' and 'description'
            tracker: Progress tracker
            semaphore: Concurrency semaphore

        Returns:
            Task result
        """
        async with semaphore:
            task_id = task_data.get("id", "unknown")
            description = task_data.get("description", "")

            tracker.increment(success=False, current_item=task_id)

            try:
                initial_state = {
                    "messages": [("user", description)],
                    "active_agent": "Coder",
                    "loop_count": 0,
                    "validator_ok": False,
                    "blocked": False,
                    "config": self.config,
                }

                final_state = await graph.ainvoke(
                    initial_state,
                    config={"recursion_limit": self.config.recursion_limit},
                )

                # Extract messages
                messages = []
                for m in final_state.get("messages", []):
                    content = getattr(m, "content", None)
                    if content:
                        messages.append(str(content))

                tracker.successful += 1
                tracker.failed -= 1  # Correct the counter

                return {
                    "task_id": task_id,
                    "status": "completed",
                    "messages": messages,
                    "validator_ok": final_state.get("validator_ok", False),
                    "blocked": final_state.get("blocked", False),
                }

            except Exception as e:
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e),
                }


class BatchValidationProcessor:
    """Validate multiple files or projects in parallel."""

    def __init__(self, check_command: str = "pytest -q"):
        """Initialize batch validation processor.

        Args:
            check_command: Validation command to run
        """
        self.check_command = check_command

    async def process(self, job: Job, queue: JobQueue) -> Dict[str, Any]:
        """Process batch validation.

        Job data format:
        {
            "targets": [
                {"id": "file1", "path": "src/module1.py"},
                {"id": "project1", "path": "projects/app1"}
            ],
            "check_command": "pytest -q",  # Optional override
            "parallel": 5,  # Optional: parallel validations
        }

        Args:
            job: Job to process
            queue: Job queue instance

        Returns:
            Validation results
        """
        targets = job.data.get("targets", [])
        check_cmd = job.data.get("check_command", self.check_command)
        parallel = min(job.data.get("parallel", 5), 10)

        if not targets:
            return {"error": "No targets provided"}

        tracker = ProgressTracker(total=len(targets))
        results = []

        # Process in parallel with semaphore
        semaphore = asyncio.Semaphore(parallel)
        tasks = [
            self._validate_target(target, check_cmd, tracker, semaphore)
            for target in targets
        ]

        validation_results = await asyncio.gather(*tasks, return_exceptions=True)

        for target, result in zip(targets, validation_results):
            if isinstance(result, Exception):
                results.append(
                    {
                        "target_id": target.get("id", "unknown"),
                        "status": "failed",
                        "error": str(result),
                    }
                )
            else:
                results.append(result)

            # Update progress
            job.progress = tracker.percentage
            job.metadata["progress"] = tracker.to_dict()
            await queue.update_job(job)

        return {
            "summary": {
                "total": tracker.total,
                "successful": tracker.successful,
                "failed": tracker.failed,
            },
            "results": results,
            "elapsed_seconds": tracker.elapsed_seconds,
        }

    async def _validate_target(
        self,
        target: Dict[str, Any],
        check_cmd: str,
        tracker: ProgressTracker,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Any]:
        """Validate a single target.

        Args:
            target: Target data with 'id' and 'path'
            check_cmd: Validation command
            tracker: Progress tracker
            semaphore: Concurrency semaphore

        Returns:
            Validation result
        """
        async with semaphore:
            target_id = target.get("id", "unknown")
            path = target.get("path", "")

            tracker.increment(success=False, current_item=target_id)

            try:
                # Run validation command
                proc = await asyncio.create_subprocess_shell(
                    f"{check_cmd} {path}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await proc.communicate()
                returncode = proc.returncode

                success = returncode == 0 or returncode == 5  # 5 = no tests

                if success:
                    tracker.successful += 1
                    tracker.failed -= 1

                return {
                    "target_id": target_id,
                    "path": path,
                    "status": "passed" if success else "failed",
                    "exit_code": returncode,
                    "stdout": stdout.decode("utf-8", errors="ignore"),
                    "stderr": stderr.decode("utf-8", errors="ignore"),
                }

            except Exception as e:
                return {
                    "target_id": target_id,
                    "path": path,
                    "status": "error",
                    "error": str(e),
                }


class BatchTestProcessor:
    """Execute tests across multiple modules in parallel."""

    async def process(self, job: Job, queue: JobQueue) -> Dict[str, Any]:
        """Process batch test execution.

        Job data format:
        {
            "modules": [
                {"id": "test1", "path": "tests/test_config.py"},
                {"id": "test2", "path": "tests/test_guardrail.py"}
            ],
            "test_command": "pytest -v",  # Optional
            "parallel": 5,  # Optional
        }

        Args:
            job: Job to process
            queue: Job queue instance

        Returns:
            Test results
        """
        modules = job.data.get("modules", [])
        test_cmd = job.data.get("test_command", "pytest -v")
        parallel = min(job.data.get("parallel", 5), 10)

        if not modules:
            return {"error": "No modules provided"}

        tracker = ProgressTracker(total=len(modules))
        results = []

        # Process in parallel
        semaphore = asyncio.Semaphore(parallel)
        tasks = [
            self._run_test_module(module, test_cmd, tracker, semaphore)
            for module in modules
        ]

        test_results = await asyncio.gather(*tasks, return_exceptions=True)

        for module, result in zip(modules, test_results):
            if isinstance(result, Exception):
                results.append(
                    {
                        "module_id": module.get("id", "unknown"),
                        "status": "error",
                        "error": str(result),
                    }
                )
            else:
                results.append(result)

            # Update progress
            job.progress = tracker.percentage
            job.metadata["progress"] = tracker.to_dict()
            await queue.update_job(job)

        return {
            "summary": {
                "total": tracker.total,
                "passed": tracker.successful,
                "failed": tracker.failed,
            },
            "results": results,
            "elapsed_seconds": tracker.elapsed_seconds,
        }

    async def _run_test_module(
        self,
        module: Dict[str, Any],
        test_cmd: str,
        tracker: ProgressTracker,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Any]:
        """Run tests for a single module.

        Args:
            module: Module data with 'id' and 'path'
            test_cmd: Test command
            tracker: Progress tracker
            semaphore: Concurrency semaphore

        Returns:
            Test result
        """
        async with semaphore:
            module_id = module.get("id", "unknown")
            path = module.get("path", "")

            tracker.increment(success=False, current_item=module_id)

            try:
                proc = await asyncio.create_subprocess_shell(
                    f"{test_cmd} {path}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await proc.communicate()
                returncode = proc.returncode

                success = returncode == 0

                if success:
                    tracker.successful += 1
                    tracker.failed -= 1

                return {
                    "module_id": module_id,
                    "path": path,
                    "status": "passed" if success else "failed",
                    "exit_code": returncode,
                    "stdout": stdout.decode("utf-8", errors="ignore"),
                    "stderr": stderr.decode("utf-8", errors="ignore"),
                }

            except Exception as e:
                return {
                    "module_id": module_id,
                    "path": path,
                    "status": "error",
                    "error": str(e),
                }


class BatchMCPProcessor:
    """Perform bulk filesystem operations through MCP."""

    async def process(self, job: Job, queue: JobQueue) -> Dict[str, Any]:
        """Process batch MCP operations.

        Job data format:
        {
            "operations": [
                {"type": "read", "path": "file1.py"},
                {"type": "write", "path": "file2.py", "content": "..."},
                {"type": "list", "path": "src/"},
                {"type": "command", "command": "ls -la"}
            ],
            "parallel": 5,  # Optional
        }

        Args:
            job: Job to process
            queue: Job queue instance

        Returns:
            Operation results
        """
        operations = job.data.get("operations", [])
        parallel = min(job.data.get("parallel", 5), 10)

        if not operations:
            return {"error": "No operations provided"}

        tracker = ProgressTracker(total=len(operations))
        results = []

        # Get MCP tools
        tools = await get_mcp_tools()
        tool_map = {tool.name: tool for tool in tools}

        # Process in parallel
        semaphore = asyncio.Semaphore(parallel)
        tasks = [
            self._execute_operation(op, tool_map, tracker, semaphore)
            for op in operations
        ]

        op_results = await asyncio.gather(*tasks, return_exceptions=True)

        for op, result in zip(operations, op_results):
            if isinstance(result, Exception):
                results.append(
                    {
                        "operation": op.get("type", "unknown"),
                        "status": "error",
                        "error": str(result),
                    }
                )
            else:
                results.append(result)

            # Update progress
            job.progress = tracker.percentage
            job.metadata["progress"] = tracker.to_dict()
            await queue.update_job(job)

        return {
            "summary": {
                "total": tracker.total,
                "successful": tracker.successful,
                "failed": tracker.failed,
            },
            "results": results,
            "elapsed_seconds": tracker.elapsed_seconds,
        }

    async def _execute_operation(
        self,
        operation: Dict[str, Any],
        tool_map: Dict[str, Any],
        tracker: ProgressTracker,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Any]:
        """Execute a single MCP operation.

        Args:
            operation: Operation data
            tool_map: Map of tool names to tools
            tracker: Progress tracker
            semaphore: Concurrency semaphore

        Returns:
            Operation result
        """
        async with semaphore:
            op_type = operation.get("type", "unknown")

            tracker.increment(success=False, current_item=op_type)

            try:
                if op_type == "read":
                    tool = tool_map.get("read_file")
                    if not tool:
                        raise ValueError("read_file tool not available")

                    result = await tool.ainvoke({"path": operation["path"]})

                elif op_type == "write":
                    tool = tool_map.get("write_file")
                    if not tool:
                        raise ValueError("write_file tool not available")

                    result = await tool.ainvoke(
                        {"path": operation["path"], "content": operation["content"]}
                    )

                elif op_type == "list":
                    tool = tool_map.get("list_directory")
                    if not tool:
                        raise ValueError("list_directory tool not available")

                    result = await tool.ainvoke({"path": operation["path"]})

                elif op_type == "command":
                    tool = tool_map.get("run_command")
                    if not tool:
                        raise ValueError("run_command tool not available")

                    result = await tool.ainvoke({"command": operation["command"]})

                else:
                    raise ValueError(f"Unknown operation type: {op_type}")

                tracker.successful += 1
                tracker.failed -= 1

                return {
                    "operation": op_type,
                    "status": "success",
                    "result": str(result),
                }

            except Exception as e:
                return {
                    "operation": op_type,
                    "status": "failed",
                    "error": str(e),
                    "operation_data": operation,
                }
