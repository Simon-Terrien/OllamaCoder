"""Celery tasks for distributed batch processing.

Each task corresponds to a batch processor operation and can be
executed by distributed Celery workers.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from celery import Task, group, chord
from celery.result import AsyncResult

from .celery_app import app
from .processors import (
    BatchAgentProcessor,
    BatchValidationProcessor,
    BatchTestProcessor,
    BatchMCPProcessor,
)
from ..core.config import RunConfig


class CallbackTask(Task):
    """Base task with callbacks for progress tracking."""

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        print(f"✅ Task {task_id} completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        print(f"❌ Task {task_id} failed: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        print(f"🔄 Task {task_id} retrying: {exc}")


@app.task(
    base=CallbackTask,
    bind=True,
    name="ollama_coder.batch.celery_tasks.process_agent_task",
)
def process_agent_task(self, task_data: Dict[str, Any], config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single agent task.

    Args:
        task_data: Task data with 'id' and 'description'
        config_dict: RunConfig as dictionary

    Returns:
        Task result dictionary
    """
    # Update progress
    self.update_state(
        state="PROGRESS",
        meta={"current": 0, "total": 1, "status": "Starting agent task..."},
    )

    try:
        # Create RunConfig from dict
        config = RunConfig(**config_dict)

        # Create processor
        processor = BatchAgentProcessor(config)

        # Run async processor in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Create mock graph for single task
            task_id = task_data.get("id", "unknown")
            description = task_data.get("description", "")

            # Import here to avoid circular dependency
            from ..core.supervisor import build_graph

            graph = loop.run_until_complete(build_graph(config))

            initial_state = {
                "messages": [("user", description)],
                "active_agent": "Coder",
                "loop_count": 0,
                "validator_ok": False,
                "blocked": False,
                "config": config,
            }

            final_state = loop.run_until_complete(
                graph.ainvoke(
                    initial_state,
                    config={"recursion_limit": config.recursion_limit},
                )
            )

            # Extract messages
            messages = []
            for m in final_state.get("messages", []):
                content = getattr(m, "content", None)
                if content:
                    messages.append(str(content))

            result = {
                "task_id": task_id,
                "status": "completed",
                "messages": messages,
                "validator_ok": final_state.get("validator_ok", False),
                "blocked": final_state.get("blocked", False),
            }

            # Update progress
            self.update_state(
                state="PROGRESS",
                meta={"current": 1, "total": 1, "status": "Completed"},
            )

            return result

        finally:
            loop.close()

    except Exception as e:
        return {
            "task_id": task_data.get("id", "unknown"),
            "status": "failed",
            "error": str(e),
        }


@app.task(
    base=CallbackTask,
    bind=True,
    name="ollama_coder.batch.celery_tasks.process_validation",
)
def process_validation(self, target: Dict[str, Any], check_command: str) -> Dict[str, Any]:
    """Process a single validation target.

    Args:
        target: Target data with 'id' and 'path'
        check_command: Validation command

    Returns:
        Validation result
    """
    self.update_state(
        state="PROGRESS",
        meta={"status": f"Validating {target.get('path', 'unknown')}..."},
    )

    try:
        processor = BatchValidationProcessor(check_command)

        # Run async validation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            import asyncio

            class MockSemaphore:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            class MockTracker:
                def increment(self, **kwargs):
                    pass

            result = loop.run_until_complete(
                processor._validate_target(
                    target, check_command, MockTracker(), MockSemaphore()
                )
            )
            return result
        finally:
            loop.close()

    except Exception as e:
        return {
            "target_id": target.get("id", "unknown"),
            "path": target.get("path", ""),
            "status": "error",
            "error": str(e),
        }


@app.task(
    base=CallbackTask,
    bind=True,
    name="ollama_coder.batch.celery_tasks.process_test",
)
def process_test(self, module: Dict[str, Any], test_command: str) -> Dict[str, Any]:
    """Process a single test module.

    Args:
        module: Module data with 'id' and 'path'
        test_command: Test command

    Returns:
        Test result
    """
    self.update_state(
        state="PROGRESS",
        meta={"status": f"Running tests in {module.get('path', 'unknown')}..."},
    )

    try:
        processor = BatchTestProcessor()

        # Run async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            import asyncio

            class MockSemaphore:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            class MockTracker:
                def increment(self, **kwargs):
                    pass

            result = loop.run_until_complete(
                processor._run_test_module(
                    module, test_command, MockTracker(), MockSemaphore()
                )
            )
            return result
        finally:
            loop.close()

    except Exception as e:
        return {
            "module_id": module.get("id", "unknown"),
            "path": module.get("path", ""),
            "status": "error",
            "error": str(e),
        }


@app.task(
    base=CallbackTask,
    bind=True,
    name="ollama_coder.batch.celery_tasks.process_mcp_operation",
)
def process_mcp_operation(self, operation: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single MCP operation.

    Args:
        operation: Operation data

    Returns:
        Operation result
    """
    op_type = operation.get("type", "unknown")

    self.update_state(
        state="PROGRESS",
        meta={"status": f"Processing {op_type} operation..."},
    )

    try:
        processor = BatchMCPProcessor()

        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from ..core.mcp_loader import get_mcp_tools

            tools = loop.run_until_complete(get_mcp_tools())
            tool_map = {tool.name: tool for tool in tools}

            class MockSemaphore:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            class MockTracker:
                def increment(self, **kwargs):
                    pass

            result = loop.run_until_complete(
                processor._execute_operation(
                    operation, tool_map, MockTracker(), MockSemaphore()
                )
            )
            return result
        finally:
            loop.close()

    except Exception as e:
        return {
            "operation": op_type,
            "status": "failed",
            "error": str(e),
            "operation_data": operation,
        }


# Batch operations using Celery groups
@app.task(
    bind=True,
    name="ollama_coder.batch.celery_tasks.batch_agent_tasks",
)
def batch_agent_tasks(self, tasks: List[Dict[str, Any]], config_dict: Dict[str, Any]) -> str:
    """Submit batch of agent tasks using Celery group.

    Args:
        tasks: List of task data
        config_dict: RunConfig as dictionary

    Returns:
        Group task ID for monitoring
    """
    job = group(
        process_agent_task.s(task, config_dict) for task in tasks
    )
    result = job.apply_async()
    return result.id


@app.task(
    bind=True,
    name="ollama_coder.batch.celery_tasks.batch_validation",
)
def batch_validation(self, targets: List[Dict[str, Any]], check_command: str) -> str:
    """Submit batch of validation tasks using Celery group.

    Args:
        targets: List of targets
        check_command: Validation command

    Returns:
        Group task ID
    """
    job = group(
        process_validation.s(target, check_command) for target in targets
    )
    result = job.apply_async()
    return result.id


@app.task(
    bind=True,
    name="ollama_coder.batch.celery_tasks.batch_tests",
)
def batch_tests(self, modules: List[Dict[str, Any]], test_command: str) -> str:
    """Submit batch of test tasks using Celery group.

    Args:
        modules: List of modules
        test_command: Test command

    Returns:
        Group task ID
    """
    job = group(
        process_test.s(module, test_command) for module in modules
    )
    result = job.apply_async()
    return result.id


@app.task(
    bind=True,
    name="ollama_coder.batch.celery_tasks.batch_mcp_operations",
)
def batch_mcp_operations(self, operations: List[Dict[str, Any]]) -> str:
    """Submit batch of MCP operations using Celery group.

    Args:
        operations: List of operations

    Returns:
        Group task ID
    """
    job = group(
        process_mcp_operation.s(operation) for operation in operations
    )
    result = job.apply_async()
    return result.id


# Utility tasks
@app.task(name="ollama_coder.batch.celery_tasks.cleanup_old_results")
def cleanup_old_results():
    """Clean up old Celery results (called by beat scheduler)."""
    # This would be implemented based on your result backend
    print("🧹 Cleaning up old results...")
    return {"cleaned": 0}


def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a Celery task.

    Args:
        task_id: Task ID

    Returns:
        Task status and results
    """
    result = AsyncResult(task_id, app=app)

    response = {
        "task_id": task_id,
        "status": result.state,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
    }

    if result.state == "PROGRESS":
        response["meta"] = result.info
    elif result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.info)

    return response


def get_group_status(group_id: str) -> Dict[str, Any]:
    """Get status of a Celery group task.

    Args:
        group_id: Group task ID

    Returns:
        Group status with individual task results
    """
    from celery.result import GroupResult

    group_result = GroupResult.restore(group_id, app=app)

    if not group_result:
        return {"error": "Group not found"}

    total = len(group_result.results)
    completed = sum(1 for r in group_result.results if r.ready())
    successful = sum(1 for r in group_result.results if r.ready() and r.successful())
    failed = sum(1 for r in group_result.results if r.ready() and not r.successful())

    results = []
    for result in group_result.results:
        if result.ready():
            if result.successful():
                results.append({"status": "completed", "result": result.result})
            else:
                results.append({"status": "failed", "error": str(result.info)})
        else:
            results.append({"status": "pending"})

    return {
        "group_id": group_id,
        "total": total,
        "completed": completed,
        "successful": successful,
        "failed": failed,
        "progress": (completed / total * 100) if total > 0 else 0,
        "results": results,
        "ready": group_result.ready(),
    }
