FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create shared directory
RUN mkdir -p /app/shared

# Copy shared modules - this will be mounted as volume

# Copy application files
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Expose MCP port (for stdio communication)
EXPOSE 7210

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app/shared'); from job_queue import JobQueue; q = JobQueue('/app/data/job_queue.db'); print('healthy' if q.get_queue_stats() else 'unhealthy')"

# Expose HTTP port
EXPOSE 3001

# Run the HTTP MCP server
CMD ["python", "http_server.py"]