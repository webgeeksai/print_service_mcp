# Task Printer MCP Queue System

A decoupled task printing system that allows Claude to queue print jobs through an MCP server, with a separate printing service that processes the queue.

## Architecture

```
Claude ──── MCP Server ──── Job Queue ──── Printing Service ──── Thermal Printer
          (Port 7210)      (SQLite)       (Bluetooth BLE)
```

### Components

1. **MCP Server**: Accepts print jobs from Claude via MCP protocol
2. **Job Queue**: SQLite-based persistent queue with status tracking
3. **Printing Service**: Polls queue and prints to thermal printer
4. **Shared Models**: Common data structures and utilities

## Features

- 🖨️ **Thermal Printer Support**: Connects to Seznik thermal printer via Bluetooth
- 📋 **Job Queue**: Persistent SQLite-based queue with retry logic
- 🔄 **Status Tracking**: Real-time job status monitoring
- 🚦 **Priority System**: High, medium, low priority job processing
- 📊 **Health Monitoring**: Queue statistics and health checks
- 🐳 **Docker Support**: Complete containerization with docker-compose
- 🧪 **Simulation Mode**: Test without actual printer hardware

## Quick Start

### 1. Environment Setup

```bash
# Copy environment file
cp .env.example .env

# Edit with your printer address
nano .env
```

### 2. Using Docker (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 3. Manual Setup

```bash
# Install dependencies for MCP server
cd mcp_server
pip install -r requirements.txt

# Install dependencies for printing service
cd ../printing_service  
pip install -r requirements.txt

# Run MCP server (in one terminal)
cd mcp_server
python server.py

# Run printing service (in another terminal)
cd printing_service
python printer.py
```

## MCP Server Tools

The MCP server provides these tools for Claude:

### `queue_print_task`
Queue a single task for printing.

**Parameters:**
- `title` (required): Task title
- `description`: Task description
- `priority`: "high", "medium", or "low" (default: "medium")
- `category`: "work", "personal", "urgent", "learning", "health", "other"
- `estimated_time`: Time estimate (e.g., "2h", "30m")
- `due_date`: ISO format date string

**Example:**
```json
{
  "title": "Review project proposal",
  "description": "Go through the technical specifications",
  "priority": "high",
  "category": "work",
  "estimated_time": "1h"
}
```

### `queue_print_tasks`
Queue multiple tasks in batch (max 10).

**Parameters:**
- `tasks`: Array of task objects (same format as single task)

### `check_job_status`
Check status of a specific job.

**Parameters:**
- `job_id`: Job ID to check

### `get_queue_status`
Get overall queue statistics and health.

### `test_queue`
Add a test job to verify the system is working.

## Configuration

### Environment Variables

- `PRINTER_ADDRESS`: Bluetooth address of your thermal printer
- `SIMULATION_MODE`: Set to `true` for testing without printer
- `DB_PATH`: Path to SQLite database file
- `POLL_INTERVAL`: Seconds between queue polling (default: 5)
- `MAX_RETRIES`: Maximum retry attempts (default: 3)

### Printer Setup

1. **Find your printer address:**
   ```bash
   # Scan for Bluetooth devices
   bluetoothctl scan on
   
   # Look for your printer (e.g., "Seznik MiniX_6109_LE")
   # Note the MAC address
   ```

2. **Update configuration:**
   ```bash
   # In .env file
   PRINTER_ADDRESS=AA:56:CE:F0:AA:49  # Your printer's address
   ```

## Development

### Running in Simulation Mode

For development without a physical printer:

```bash
export SIMULATION_MODE=true
python printing_service/printer.py
```

### Testing the Queue

```bash
# Test with Claude or manually:
python -c "
from shared.job_queue import JobQueue, PrintJob
queue = JobQueue('test.db')
job = PrintJob({'title': 'Test Task', 'priority': 'high'})
job_id = queue.add_job(job)
print(f'Added job: {job_id}')
"
```

### Monitoring

```bash
# View queue status
docker-compose exec mcp-server python -c "
from shared.job_queue import JobQueue
queue = JobQueue('/app/data/job_queue.db')
print(queue.get_queue_stats())
"

# View printing service logs
docker-compose logs -f printing-service
```

## Troubleshooting

### Common Issues

1. **Bluetooth Permission Denied**
   - Run with `privileged: true` in docker-compose
   - Ensure user is in `bluetooth` group on host

2. **MCP Connection Issues**
   - Check port 7210 availability
   - Verify MCP server is running with stdio mode

3. **Printer Connection Failed**
   - Verify printer is powered on and discoverable
   - Check Bluetooth address is correct
   - Try pairing manually first

4. **Database Lock Errors**
   - Ensure only one instance accesses the database
   - Check file permissions on database path

### Debug Mode

```bash
# Enable verbose logging
export PYTHONPATH=/app/shared
python printing_service/printer.py --debug
```

## API Integration

The MCP server communicates with Claude using the Model Context Protocol. No direct HTTP API is exposed.

### Adding to Claude Desktop

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "task-printer-queue": {
      "command": "python",
      "args": ["/path/to/task_printer_mcp_queue/mcp_server/server.py"],
      "env": {
        "DB_PATH": "/path/to/data/job_queue.db"
      }
    }
  }
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with simulation mode
5. Submit a pull request

## License

MIT License - see LICENSE file for details.