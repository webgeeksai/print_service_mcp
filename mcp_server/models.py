#!/usr/bin/env python3
"""
Shared models for Task Printer MCP Queue System
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TaskCategory(str, Enum):
    WORK = "work"
    PERSONAL = "personal"
    URGENT = "urgent"
    LEARNING = "learning"
    HEALTH = "health"
    OTHER = "other"

class TaskPrintRequest(BaseModel):
    """Request model for printing a task"""
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="Task priority")
    category: Optional[TaskCategory] = Field(TaskCategory.OTHER, description="Task category")
    due_date: Optional[datetime] = Field(None, description="Due date")
    estimated_time: Optional[str] = Field(None, description="Estimated time to complete")
    task_id: Optional[str] = Field(None, description="Custom task ID")

class BatchPrintRequest(BaseModel):
    """Request model for batch printing multiple tasks"""
    tasks: List[TaskPrintRequest] = Field(..., max_items=10, description="List of tasks to print")

class PrintJobResponse(BaseModel):
    """Response model for print job submission"""
    success: bool
    job_id: str
    message: str
    estimated_completion: Optional[datetime] = None

class BatchPrintJobResponse(BaseModel):
    """Response model for batch print job submission"""
    success: bool
    job_ids: List[str]
    message: str
    total_jobs: int

class JobStatusResponse(BaseModel):
    """Response model for job status"""
    job_id: str
    status: str
    title: str
    created_at: datetime
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int
    progress: Optional[str] = None

class QueueStatsResponse(BaseModel):
    """Response model for queue statistics"""
    total_jobs: int
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    retry: int = 0
    jobs_last_24h: int
    queue_health: str