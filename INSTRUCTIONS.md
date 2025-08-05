# Task Printer MCP Queue - Quick Start Guide

## 🚀 How to Run the System

The system has **two parts** that need to run simultaneously:

1. **Printing Service** (Python script) - Polls the queue and prints to your Seznik printer
2. **MCP Server** (Docker Compose) - Accepts print jobs from Claude

---

## 📝 Step 1: Start the Printing Service

Open a terminal and navigate to the project directory:

```bash
cd /Users/webgeeks/projects/task_printer_mcp_queue
```

Run the printing service:

```bash
python3 printing_service/printer.py
```

**✅ You should see:**
```
🖨️ Task Printer Service Starting...
🔧 Configuration:
   DB Path: ./data/job_queue.db
   Printer: AA56CEF0-AA49-FD9B-0331-2C91D3622AA9
   Simulation: false
🖨️ Printer configured: AA56CEF0-AA49-FD9B-0331-2C91D3622AA9
🚀 Starting Task Printer Service...
📊 Queue status: 0 jobs waiting, 0 completed
```

**Keep this terminal open** - the service will continuously poll for new print jobs.

---

## 🐳 Step 2: Start the MCP Server (Docker Compose)

Open a **new terminal** and navigate to the project directory:

```bash
cd /Users/webgeeks/projects/task_printer_mcp_queue
```

Start the MCP server with Docker Compose:

```bash
# Start the MCP server
docker-compose up --build

# Or run in background:
docker-compose up -d --build
```

**✅ You should see the MCP server start without errors.**

**To stop the MCP server:**
```bash
docker-compose down
```

---

## 🧪 Step 3: Test the System

Open a **third terminal** to test:

```bash
cd /Users/webgeeks/projects/task_printer_mcp_queue

# Add a test job to the queue
python3 -c "
import sys
sys.path.insert(0, 'shared')
from job_queue import JobQueue, PrintJob

queue = JobQueue('./data/job_queue.db')
job_data = {
    'title': 'Test Task from Instructions',
    'description': 'Testing the complete system',
    'priority': 'high',
    'category': 'work',
    'estimated_time': '5min'
}

job = PrintJob(job_data)
job_id = queue.add_job(job)
print(f'✅ Added test job: {job_id}')
"
```

**Watch the printing service terminal** - you should see it process and print the job!

---

## 🔧 Troubleshooting

### Printing Service Issues:

1. **"Module not found" errors:**
   ```bash
   pip3 install bleak Pillow python-dotenv pydantic
   ```

2. **Bluetooth permission denied:**
   - Make sure your printer is on and discoverable
   - Try connecting to the printer manually first

3. **Database errors:**
   ```bash
   mkdir -p data
   chmod 755 data
   ```

### MCP Server Issues:

1. **Docker build fails:**
   ```bash
   # Install Docker dependencies
   pip3 install mcp pydantic
   ```

2. **Container won't start:**
   ```bash
   # Check if data volume exists
   mkdir -p data
   ```

---

## 📱 Connecting to Claude

Once both services are running, you can connect Claude to the MCP server via URL.

### Option 1: Using Claude Code (Remote MCP)

In Claude Code, add the remote MCP server:

```bash
claude mcp add --transport http task-printer-queue http://localhost:3001/mcp
```

Or if connecting from another machine, replace `localhost` with your server's IP address:

```bash
claude mcp add --transport http task-printer-queue http://YOUR_SERVER_IP:3001/mcp
```

### Option 2: Direct URL Access

You can also access the MCP server directly at:
- **MCP Endpoint**: `http://localhost:3001/mcp`
- **Health Check**: `http://localhost:3001/health`
- **Server Info**: `http://localhost:3001/`

### Option 3: Claude Desktop Configuration (Legacy)

For older Claude Desktop versions:

```json
{
  "mcpServers": {
    "task-printer-queue": {
      "command": "docker-compose",
      "args": [
        "-f", "/Users/webgeeks/projects/task_printer_mcp_queue/docker-compose.yml",
        "run", "--rm", "mcp-server"
      ],
      "cwd": "/Users/webgeeks/projects/task_printer_mcp_queue"
    }
  }
}
```

**Then in Claude, you can say:**
- "Print a task card for 'Review project proposal' with high priority"
- "Queue 3 tasks for printing: task1, task2, task3"
- "Check the status of my print queue"

---

## 🎯 Quick Commands Reference

**Start Printing Service:**
```bash
python3 printing_service/printer.py
```

**Start MCP Server:**
```bash
docker-compose up --build
```

**Stop MCP Server:**
```bash
docker-compose down
```

**Add Test Job:**
```bash
python3 -c "import sys; sys.path.insert(0, 'shared'); from job_queue import JobQueue, PrintJob; queue = JobQueue('./data/job_queue.db'); job = PrintJob({'title': 'Test Task', 'priority': 'high'}); print(f'Added: {queue.add_job(job)}')"
```

**Check Queue Status:**
```bash
python3 -c "import sys; sys.path.insert(0, 'shared'); from job_queue import JobQueue; queue = JobQueue('./data/job_queue.db'); print(queue.get_queue_stats())"
```

---

🎉 **That's it!** Your physical Kanban printer is ready to receive tasks from Claude!