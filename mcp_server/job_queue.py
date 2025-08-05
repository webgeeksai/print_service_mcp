#!/usr/bin/env python3
"""
Job Queue System for Task Printer MCP
Handles job persistence, status tracking, and queue management
"""

import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import threading
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"

class JobPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

class PrintJob:
    def __init__(self, job_data: Dict[str, Any], job_id: str = None):
        self.job_id = job_id or str(uuid.uuid4())
        self.job_type = job_data.get('job_type', 'print_task')
        self.title = job_data.get('title', 'Untitled Task')
        self.description = job_data.get('description', '')
        self.priority = job_data.get('priority', 'medium')
        self.category = job_data.get('category', 'other')
        self.estimated_time = job_data.get('estimated_time', '')
        self.due_date = job_data.get('due_date')
        self.created_at = datetime.now()
        self.status = JobStatus.PENDING
        self.retry_count = 0
        self.max_retries = 3
        self.error_message = None
        self.processed_at = None
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'job_type': self.job_type,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'category': self.category,
            'estimated_time': self.estimated_time,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'created_at': self.created_at.isoformat(),
            'status': self.status.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'error_message': self.error_message,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PrintJob':
        job = cls(data, data['job_id'])
        job.created_at = datetime.fromisoformat(data['created_at'])
        job.status = JobStatus(data['status'])
        job.retry_count = data.get('retry_count', 0)
        job.max_retries = data.get('max_retries', 3)
        job.error_message = data.get('error_message')
        if data.get('processed_at'):
            job.processed_at = datetime.fromisoformat(data['processed_at'])
        if data.get('due_date'):
            job.due_date = datetime.fromisoformat(data['due_date'])
        return job

class JobQueue:
    def __init__(self, db_path: str = "job_queue.db"):
        self.db_path = Path(db_path)
        self.lock = threading.Lock()
        self._init_database()
        
    def _init_database(self):
        """Initialize the SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS print_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT,
                    category TEXT,
                    estimated_time TEXT,
                    due_date TEXT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    error_message TEXT,
                    processed_at TEXT,
                    job_data TEXT
                )
            """)
            
            # Create index for efficient queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON print_jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON print_jobs(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON print_jobs(priority)")
            
            conn.commit()
            
    def add_job(self, job: PrintJob) -> str:
        """Add a new print job to the queue"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO print_jobs (
                        job_id, job_type, title, description, priority, category,
                        estimated_time, due_date, created_at, status, retry_count,
                        max_retries, error_message, processed_at, job_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job.job_id, job.job_type, job.title, job.description,
                    job.priority, job.category, job.estimated_time,
                    job.due_date.isoformat() if job.due_date else None,
                    job.created_at.isoformat(), job.status.value,
                    job.retry_count, job.max_retries, job.error_message,
                    job.processed_at.isoformat() if job.processed_at else None,
                    json.dumps(job.to_dict())
                ))
                conn.commit()
                
        logger.info(f"Added job {job.job_id}: {job.title}")
        return job.job_id
    
    def get_next_job(self) -> Optional[PrintJob]:
        """Get the next pending job based on priority and creation time"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                # Priority order: high=3, medium=2, low=1
                priority_order = "CASE priority WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END"
                
                cursor = conn.execute(f"""
                    SELECT job_data FROM print_jobs 
                    WHERE status IN ('pending', 'retry')
                    ORDER BY {priority_order} DESC, created_at ASC
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if row:
                    job_data = json.loads(row[0])
                    return PrintJob.from_dict(job_data)
                    
        return None
    
    def update_job_status(self, job_id: str, status: JobStatus, error_message: str = None):
        """Update job status"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                processed_at = datetime.now().isoformat() if status in [JobStatus.COMPLETED, JobStatus.FAILED] else None
                
                conn.execute("""
                    UPDATE print_jobs 
                    SET status = ?, error_message = ?, processed_at = ?
                    WHERE job_id = ?
                """, (status.value, error_message, processed_at, job_id))
                
                # Update job_data as well
                cursor = conn.execute("SELECT job_data FROM print_jobs WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                if row:
                    job_data = json.loads(row[0])
                    job_data['status'] = status.value
                    job_data['error_message'] = error_message
                    job_data['processed_at'] = processed_at
                    
                    conn.execute("UPDATE print_jobs SET job_data = ? WHERE job_id = ?", 
                               (json.dumps(job_data), job_id))
                
                conn.commit()
                
        logger.info(f"Updated job {job_id} status to {status.value}")
    
    def increment_retry_count(self, job_id: str) -> bool:
        """Increment retry count and set status to retry if under max retries"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT retry_count, max_retries FROM print_jobs WHERE job_id = ?
                """, (job_id,))
                
                row = cursor.fetchone()
                if row:
                    retry_count, max_retries = row
                    new_retry_count = retry_count + 1
                    
                    if new_retry_count <= max_retries:
                        conn.execute("""
                            UPDATE print_jobs 
                            SET retry_count = ?, status = ?
                            WHERE job_id = ?
                        """, (new_retry_count, JobStatus.RETRY.value, job_id))
                        conn.commit()
                        logger.info(f"Job {job_id} set for retry ({new_retry_count}/{max_retries})")
                        return True
                    else:
                        self.update_job_status(job_id, JobStatus.FAILED, f"Max retries ({max_retries}) exceeded")
                        return False
                        
        return False
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and details"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT job_data FROM print_jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            # Count by status
            cursor = conn.execute("""
                SELECT status, COUNT(*) FROM print_jobs GROUP BY status
            """)
            for status, count in cursor.fetchall():
                stats[status] = count
                
            # Total jobs
            cursor = conn.execute("SELECT COUNT(*) FROM print_jobs")
            stats['total_jobs'] = cursor.fetchone()[0]
            
            # Jobs in last 24 hours
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            cursor = conn.execute("""
                SELECT COUNT(*) FROM print_jobs WHERE created_at > ?
            """, (yesterday,))
            stats['jobs_last_24h'] = cursor.fetchone()[0]
            
            return stats
    
    def cleanup_old_jobs(self, days: int = 7):
        """Clean up completed/failed jobs older than specified days"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM print_jobs 
                    WHERE status IN ('completed', 'failed') 
                    AND created_at < ?
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
        logger.info(f"Cleaned up {deleted_count} old jobs")
        return deleted_count