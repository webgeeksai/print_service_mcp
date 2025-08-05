#!/usr/bin/env python3
"""
FastMCP Server for Task Printer Queue System
Uses the FastMCP library for proper MCP implementation
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add shared directory to path
shared_path = Path(__file__).parent.parent / "shared"
if shared_path.exists():
    sys.path.insert(0, str(shared_path))
else:
    sys.path.insert(0, "/app/shared")

try:
    from fastmcp import FastMCP
except ImportError:
    print("FastMCP not installed. Install with: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

# Try different import paths for shared modules
try:
    from job_queue import JobQueue, PrintJob, JobStatus
except ImportError:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
        from job_queue import JobQueue, PrintJob, JobStatus
    except ImportError as e:
        print(f"Error importing shared modules: {e}", file=sys.stderr)
        raise

# Configuration
DB_PATH = os.getenv("DB_PATH", "/app/data/job_queue.db")

# Initialize FastMCP server
mcp = FastMCP("Task Printer Queue")

# Initialize job queue
job_queue = JobQueue(DB_PATH)

@mcp.tool()
def queue_print_task(
    title: str,
    description: str = "",
    priority: str = "medium",
    category: str = "other",
    estimated_time: str = "",
    due_date: str = ""
) -> str:
    """
    Queue a single task for printing to the thermal printer.
    
    Args:
        title: Task title (required)
        description: Task description (optional)
        priority: Task priority level - one of: high, medium, low
        category: Task category - one of: work, personal, urgent, learning, health, other
        estimated_time: Estimated time to complete (e.g., '2h', '30m')
        due_date: Due date in ISO format (e.g., '2024-12-30T14:00:00')
    
    Returns:
        Status message with job ID
    """
    try:
        # Parse due_date if provided
        parsed_due_date = None
        if due_date:
            try:
                parsed_due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except ValueError:
                parsed_due_date = None
        
        # Validate priority
        if priority not in ['high', 'medium', 'low']:
            priority = 'medium'
            
        # Validate category
        if category not in ['work', 'personal', 'urgent', 'learning', 'health', 'other']:
            category = 'other'
        
        # Create job data
        job_data = {
            'title': title,
            'description': description,
            'priority': priority,
            'category': category,
            'estimated_time': estimated_time,
            'due_date': parsed_due_date
        }
        
        # Create and add job
        job = PrintJob(job_data)
        job_id = job_queue.add_job(job)
        
        return f"✅ Task '{title}' queued successfully!\n📋 Job ID: {job_id}\n🚦 Priority: {priority}\n📁 Category: {category}\n⏱️ Estimated time: {estimated_time or 'not specified'}\n🖨️ The task will be printed when the printer is available."
        
    except Exception as e:
        return f"❌ Failed to queue task: {str(e)}"

@mcp.tool()
def queue_print_tasks(tasks: list) -> str:
    """
    Queue multiple tasks for printing in batch (max 10 tasks).
    
    Args:
        tasks: List of task dictionaries, each containing:
            - title (required): Task title
            - description (optional): Task description  
            - priority (optional): high, medium, or low
            - category (optional): work, personal, urgent, learning, health, other
            - estimated_time (optional): Time estimate
            - due_date (optional): ISO format date
    
    Returns:
        Status message with job IDs
    """
    try:
        if not tasks:
            return "❌ No tasks provided"
        
        if len(tasks) > 10:
            return "❌ Too many tasks (max 10 per batch)"

        job_ids = []
        for task_data in tasks:
            if not isinstance(task_data, dict):
                continue
                
            title = task_data.get('title', 'Untitled Task')
            
            # Parse due_date if provided
            if task_data.get('due_date'):
                try:
                    task_data['due_date'] = datetime.fromisoformat(task_data['due_date'].replace('Z', '+00:00'))
                except ValueError:
                    task_data['due_date'] = None
            
            # Validate and set defaults
            task_data.setdefault('description', '')
            task_data.setdefault('priority', 'medium')
            task_data.setdefault('category', 'other')
            task_data.setdefault('estimated_time', '')
            
            job = PrintJob(task_data)
            job_id = job_queue.add_job(job)
            job_ids.append(job_id)
        
        return f"✅ Successfully queued {len(job_ids)} tasks for printing!\n📋 Job IDs: {', '.join(job_ids[:3])}{'...' if len(job_ids) > 3 else ''}\n🖨️ Tasks will be printed in priority order when the printer is available."
        
    except Exception as e:
        return f"❌ Failed to queue tasks: {str(e)}"

@mcp.tool()
def check_job_status(job_id: str) -> str:
    """
    Check the status of a specific print job.
    
    Args:
        job_id: Job ID to check status for
    
    Returns:
        Detailed job status information
    """
    try:
        if not job_id:
            return "❌ Job ID is required"
        
        job_data = job_queue.get_job_status(job_id)
        if not job_data:
            return f"❌ Job {job_id} not found"
        
        status_emoji = {
            'pending': '⏳',
            'processing': '🖨️',
            'completed': '✅',
            'failed': '❌',
            'retry': '🔄'
        }
        
        emoji = status_emoji.get(job_data['status'], '❓')
        
        status_text = f"{emoji} **Job Status: {job_data['status'].upper()}**\n\n"
        status_text += f"📋 **Job ID**: {job_data['job_id']}\n"
        status_text += f"📝 **Title**: {job_data['title']}\n"
        status_text += f"🚦 **Priority**: {job_data['priority']}\n"
        status_text += f"📁 **Category**: {job_data['category']}\n"
        status_text += f"🕐 **Created**: {job_data['created_at'][:19]}\n"
        
        if job_data.get('processed_at'):
            status_text += f"✨ **Processed**: {job_data['processed_at'][:19]}\n"
        
        if job_data.get('error_message'):
            status_text += f"💥 **Error**: {job_data['error_message']}\n"
        
        if job_data.get('retry_count', 0) > 0:
            status_text += f"🔄 **Retries**: {job_data['retry_count']}/{job_data.get('max_retries', 3)}\n"
        
        return status_text
        
    except Exception as e:
        return f"❌ Error checking job status: {str(e)}"

@mcp.tool()
def get_queue_status() -> str:
    """
    Get overall queue status and statistics.
    
    Returns:
        Current queue statistics and health status
    """
    try:
        stats = job_queue.get_queue_stats()
        
        status_text = f"📊 **Print Queue Status**\n\n"
        status_text += f"📋 **Total Jobs**: {stats.get('total_jobs', 0)}\n"
        status_text += f"⏳ **Pending**: {stats.get('pending', 0)}\n"
        status_text += f"🖨️ **Processing**: {stats.get('processing', 0)}\n"
        status_text += f"✅ **Completed**: {stats.get('completed', 0)}\n"
        status_text += f"❌ **Failed**: {stats.get('failed', 0)}\n"
        status_text += f"🔄 **Retry**: {stats.get('retry', 0)}\n"
        status_text += f"📈 **Last 24h**: {stats.get('jobs_last_24h', 0)}\n\n"
        
        queue_size = stats.get('pending', 0) + stats.get('retry', 0)
        if queue_size == 0:
            status_text += "🟢 **Queue is empty** - Ready for new jobs!"
        elif queue_size < 5:
            status_text += f"🟡 **{queue_size} jobs waiting** - Normal processing"
        else:
            status_text += f"🔴 **{queue_size} jobs waiting** - Queue is busy"
        
        return status_text
        
    except Exception as e:
        return f"❌ Error getting queue status: {str(e)}"

@mcp.tool()
def test_queue() -> str:
    """
    Add a test print job to verify the queue system.
    
    Returns:
        Status message with test job ID
    """
    try:
        test_job_data = {
            'title': 'Test Print Job',
            'description': 'This is a test job to verify the queue system is working correctly.',
            'priority': 'high',
            'category': 'other',
            'estimated_time': '1min'
        }
        
        job = PrintJob(test_job_data)
        job_id = job_queue.add_job(job)
        
        return f"✅ Test job created successfully!\n📋 Job ID: {job_id}\n🧪 This test job will be processed by the printing service.\n📊 Check job status with: check_job_status(job_id='{job_id}')"
        
    except Exception as e:
        return f"❌ Failed to create test job: {str(e)}"

# Resource handlers
@mcp.resource("task-printer-queue://status")
def get_queue_resource() -> str:
    """Get current queue status as JSON resource."""
    try:
        stats = job_queue.get_queue_stats()
        stats['queue_health'] = 'healthy' if stats.get('total_jobs', 0) < 100 else 'busy'
        import json
        return json.dumps(stats, indent=2)
    except Exception as e:
        import json
        return json.dumps({"error": str(e)})

@mcp.resource("task-printer-queue://health")
def get_health_resource() -> str:
    """Get system health as JSON resource."""
    try:
        stats = job_queue.get_queue_stats()
        health = {
            "status": "healthy",
            "queue_size": stats.get('pending', 0) + stats.get('retry', 0),
            "processing": stats.get('processing', 0),
            "last_check": datetime.now().isoformat()
        }
        import json
        return json.dumps(health, indent=2)
    except Exception as e:
        import json
        return json.dumps({"error": str(e)})

def main():
    """Main entry point"""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    print(f"🌐 Starting Task Printer FastMCP Server", file=sys.stderr)
    print(f"📊 Database: {DB_PATH}", file=sys.stderr)
    
    # Run the FastMCP server
    mcp.run()

if __name__ == "__main__":
    main()