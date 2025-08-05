from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class Priority(str, Enum):
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
    title: str
    description: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    category: Optional[TaskCategory] = TaskCategory.OTHER
    due_date: Optional[datetime] = None
    assignee: Optional[str] = None
    task_id: Optional[str] = None
    estimated_time: Optional[str] = None  # e.g., "2h", "30m"
    
class PrintResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[str] = None