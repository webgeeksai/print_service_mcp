FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Bluetooth and fonts
RUN apt-get update && apt-get install -y \
    bluez \
    bluez-tools \
    libbluetooth-dev \
    fonts-dejavu-core \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create shared directory
RUN mkdir -p /app/shared

# Copy shared modules
COPY ../shared/ /app/shared/

# Copy thermal printer modules (if available)
RUN mkdir -p /app/printer_modules

# Copy application files
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app/shared'); from job_queue import JobQueue; q = JobQueue('/app/data/job_queue.db'); print('healthy')"

# Run the printing service
CMD ["python", "printer.py"]