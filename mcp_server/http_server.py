#!/usr/bin/env python3
"""
HTTP MCP Server for Task Printer Queue System
Provides HTTP endpoint for remote Claude connections
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Add shared directory to path
shared_path = Path(__file__).parent.parent / "shared"
if shared_path.exists():
    sys.path.insert(0, str(shared_path))
else:
    # In Docker, shared is mounted as volume
    sys.path.insert(0, "/app/shared")

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Resource, Tool, TextContent

# Try different import paths for shared modules
try:
    from job_queue import JobQueue, PrintJob, JobStatus
    from models import (
        TaskPrintRequest, BatchPrintRequest, PrintJobResponse, 
        BatchPrintJobResponse, JobStatusResponse, QueueStatsResponse
    )
except ImportError:
    # Try absolute imports
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
        from job_queue import JobQueue, PrintJob, JobStatus
        from models import (
            TaskPrintRequest, BatchPrintRequest, PrintJobResponse, 
            BatchPrintJobResponse, JobStatusResponse, QueueStatsResponse
        )
    except ImportError as e:
        print(f"Error importing shared modules: {e}")
        print(f"Python path: {sys.path}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Files in /app: {os.listdir('/app') if os.path.exists('/app') else 'N/A'}")
        print(f"Files in /app/shared: {os.listdir('/app/shared') if os.path.exists('/app/shared') else 'N/A'}")
        raise

# Configuration
SERVER_NAME = "task-printer-queue"
SERVER_VERSION = "1.0.0"
DB_PATH = os.getenv("DB_PATH", "/app/data/job_queue.db")
PORT = int(os.getenv("PORT", "3001"))

class TaskPrinterHTTPServer:
    def __init__(self):
        self.app = FastAPI(
            title="Task Printer MCP Server",
            description="MCP Server for Task Printer Queue System",
            version=SERVER_VERSION
        )
        self.mcp_server = Server(SERVER_NAME)
        self.job_queue = JobQueue(DB_PATH)
        self.sessions = {}  # Track MCP sessions
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self.setup_mcp_handlers()
        self.setup_http_routes()

    def setup_mcp_handlers(self):
        @self.mcp_server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available resources"""
            return [
                Resource(
                    uri="task-printer-queue://status",
                    name="Queue Status",
                    description="Current status and statistics of the print job queue",
                    mimeType="application/json",
                ),
                Resource(
                    uri="task-printer-queue://jobs",
                    name="Recent Jobs",
                    description="List of recent print jobs and their status",
                    mimeType="application/json",
                ),
                Resource(
                    uri="task-printer-queue://health",
                    name="System Health",
                    description="Health check of the queue system",
                    mimeType="application/json",
                ),
            ]

        @self.mcp_server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a specific resource"""
            try:
                if uri == "task-printer-queue://status":
                    stats = self.job_queue.get_queue_stats()
                    stats['queue_health'] = 'healthy' if stats.get('total_jobs', 0) < 100 else 'busy'
                    return json.dumps(stats, indent=2)
                    
                elif uri == "task-printer-queue://jobs":
                    stats = self.job_queue.get_queue_stats()
                    return json.dumps({
                        "recent_jobs": "Feature coming soon",
                        "queue_summary": stats
                    }, indent=2)
                    
                elif uri == "task-printer-queue://health":
                    stats = self.job_queue.get_queue_stats()
                    health = {
                        "status": "healthy",
                        "queue_size": stats.get('pending', 0) + stats.get('retry', 0),
                        "processing": stats.get('processing', 0),
                        "last_check": datetime.now().isoformat()
                    }
                    return json.dumps(health, indent=2)
                    
                else:
                    raise ValueError(f"Unknown resource: {uri}")
                    
            except Exception as e:
                return json.dumps({"error": str(e)})

        @self.mcp_server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="queue_print_task",
                    description="Queue a single task for printing to the thermal printer",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Task title (required)"
                            },
                            "description": {
                                "type": "string",
                                "description": "Task description (optional)"
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Task priority level",
                                "default": "medium"
                            },
                            "category": {
                                "type": "string",
                                "enum": ["work", "personal", "urgent", "learning", "health", "other"],
                                "description": "Task category",
                                "default": "other"
                            },
                            "estimated_time": {
                                "type": "string",
                                "description": "Estimated time to complete (e.g., '2h', '30m')"
                            },
                            "due_date": {
                                "type": "string",
                                "description": "Due date in ISO format (e.g., '2024-12-30T14:00:00')"
                            }
                        },
                        "required": ["title"]
                    }
                ),
                Tool(
                    name="queue_print_tasks",
                    description="Queue multiple tasks for printing in batch (max 10 tasks)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tasks": {
                                "type": "array",
                                "description": "Array of tasks to queue for printing",
                                "maxItems": 10,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string", "description": "Task title"},
                                        "description": {"type": "string", "description": "Task description"},
                                        "priority": {
                                            "type": "string", 
                                            "enum": ["high", "medium", "low"],
                                            "default": "medium"
                                        },
                                        "category": {
                                            "type": "string",
                                            "enum": ["work", "personal", "urgent", "learning", "health", "other"],
                                            "default": "other"
                                        },
                                        "estimated_time": {"type": "string"},
                                        "due_date": {"type": "string"}
                                    },
                                    "required": ["title"]
                                }
                            }
                        },
                        "required": ["tasks"]
                    }
                ),
                Tool(
                    name="check_job_status",
                    description="Check the status of a specific print job",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "Job ID to check status for"
                            }
                        },
                        "required": ["job_id"]
                    }
                ),
                Tool(
                    name="get_queue_status",
                    description="Get overall queue status and statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="test_queue",
                    description="Add a test print job to verify the queue system",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                )
            ]

        @self.mcp_server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            try:
                if name == "queue_print_task":
                    return await self._queue_print_task(arguments)
                elif name == "queue_print_tasks":
                    return await self._queue_print_tasks(arguments)
                elif name == "check_job_status":
                    return await self._check_job_status(arguments)
                elif name == "get_queue_status":
                    return await self._get_queue_status()
                elif name == "test_queue":
                    return await self._test_queue()
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

    async def _queue_print_task(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Queue a single print task"""
        try:
            # Parse due_date if provided
            if arguments.get('due_date'):
                try:
                    arguments['due_date'] = datetime.fromisoformat(arguments['due_date'].replace('Z', '+00:00'))
                except ValueError:
                    arguments['due_date'] = None
            
            # Create print job
            job = PrintJob(arguments)
            job_id = self.job_queue.add_job(job)
            
            return [TextContent(
                type="text",
                text=f"✅ Task '{arguments['title']}' queued successfully!\n"
                     f"📋 Job ID: {job_id}\n"
                     f"🚦 Priority: {arguments.get('priority', 'medium')}\n"
                     f"📁 Category: {arguments.get('category', 'other')}\n"
                     f"⏱️ Estimated time: {arguments.get('estimated_time', 'not specified')}\n"
                     f"🖨️ The task will be printed when the printer is available."
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Failed to queue task: {str(e)}"
            )]

    async def _queue_print_tasks(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Queue multiple print tasks"""
        try:
            tasks = arguments.get("tasks", [])
            if not tasks:
                return [TextContent(type="text", text="❌ No tasks provided")]
            
            if len(tasks) > 10:
                return [TextContent(type="text", text="❌ Too many tasks (max 10 per batch)")]

            job_ids = []
            for task_data in tasks:
                # Parse due_date if provided
                if task_data.get('due_date'):
                    try:
                        task_data['due_date'] = datetime.fromisoformat(task_data['due_date'].replace('Z', '+00:00'))
                    except ValueError:
                        task_data['due_date'] = None
                
                job = PrintJob(task_data)
                job_id = self.job_queue.add_job(job)
                job_ids.append(job_id)
            
            return [TextContent(
                type="text",
                text=f"✅ Successfully queued {len(job_ids)} tasks for printing!\n"
                     f"📋 Job IDs: {', '.join(job_ids[:3])}{'...' if len(job_ids) > 3 else ''}\n"
                     f"🖨️ Tasks will be printed in priority order when the printer is available.\n"
                     f"📊 Queue position: These jobs are now in the print queue."
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Failed to queue tasks: {str(e)}"
            )]

    async def _check_job_status(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Check the status of a specific job"""
        try:
            job_id = arguments.get("job_id")
            if not job_id:
                return [TextContent(type="text", text="❌ Job ID is required")]
            
            job_data = self.job_queue.get_job_status(job_id)
            if not job_data:
                return [TextContent(type="text", text=f"❌ Job {job_id} not found")]
            
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
            
            return [TextContent(type="text", text=status_text)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error checking job status: {str(e)}"
            )]

    async def _get_queue_status(self) -> List[TextContent]:
        """Get overall queue status"""
        try:
            stats = self.job_queue.get_queue_stats()
            
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
            
            return [TextContent(type="text", text=status_text)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Error getting queue status: {str(e)}"
            )]

    async def _test_queue(self) -> List[TextContent]:
        """Add a test job to the queue"""
        try:
            test_job_data = {
                'title': 'Test Print Job',
                'description': 'This is a test job to verify the queue system is working correctly.',
                'priority': 'high',
                'category': 'other',
                'estimated_time': '1min'
            }
            
            job = PrintJob(test_job_data)
            job_id = self.job_queue.add_job(job)
            
            return [TextContent(
                type="text",
                text=f"✅ Test job created successfully!\n"
                     f"📋 Job ID: {job_id}\n"
                     f"🧪 This test job will be processed by the printing service.\n"
                     f"📊 Check job status with: check_job_status(job_id='{job_id}')"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Failed to create test job: {str(e)}"
            )]

    def setup_http_routes(self):
        @self.app.get("/")
        async def root():
            return {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
                "description": "Task Printer MCP Queue System",
                "status": "healthy"
            }

        @self.app.get("/health")
        async def health():
            stats = self.job_queue.get_queue_stats()
            return {
                "status": "healthy",
                "queue_size": stats.get('pending', 0) + stats.get('retry', 0),
                "total_jobs": stats.get('total_jobs', 0),
                "timestamp": datetime.now().isoformat()
            }

        @self.app.post("/mcp")
        async def mcp_endpoint(request: Request):
            """Main MCP endpoint for streamable HTTP transport"""
            try:
                # Get session ID from headers or create new one
                session_id = request.headers.get("x-mcp-session-id", str(uuid.uuid4()))
                
                content_type = request.headers.get("content-type", "")
                
                if "application/json" in content_type:
                    # Handle JSON MCP message
                    data = await request.json()
                    
                    # Process MCP message through the server
                    # This is a simplified implementation - in production you'd want
                    # proper MCP message routing and session handling
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": {
                            "status": "received",
                            "session_id": session_id
                        }
                    }
                else:
                    raise HTTPException(status_code=400, detail="Unsupported content type")
                    
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    async def run(self):
        """Run the HTTP MCP server"""
        # Ensure data directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        print(f"🌐 Starting Task Printer HTTP MCP Server on port {PORT}")
        print(f"📊 Database: {DB_PATH}")
        print(f"🔗 MCP Endpoint: http://localhost:{PORT}/mcp")
        print(f"💊 Health Check: http://localhost:{PORT}/health")
        
        config = uvicorn.Config(
            app=self.app,
            host="0.0.0.0",
            port=PORT,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()

async def main():
    """Main entry point"""
    server = TaskPrinterHTTPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())