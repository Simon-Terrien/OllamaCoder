from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel


class PlanStep(BaseModel):
    description: str
    specialty: Literal["backend", "frontend", "tests", "devops", "security", "docs", "general"] = "general"


class DevPlan(BaseModel):
    steps: List[PlanStep]
    needs_docs: bool = False


class Patch(BaseModel):
    path: str
    new_content: str


class CodeResult(BaseModel):
    applied: bool = False
    patches: List[Patch] = []
    notes: str = ""
    suggested_docs: Optional[str] = None


class DocsResult(BaseModel):
    summary: str
    files_updated: List[str] = []


class OrchestrationSummary(BaseModel):
    plan: DevPlan
    code_results: List[CodeResult]
    docs_result: Optional[DocsResult] = None
    notes: str = ""
