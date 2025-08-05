#!/bin/bash

# Task Printer MCP Queue Setup Script
# Sets up the complete system on Ubuntu server

set -e  # Exit on any error

echo "🖨️ Task Printer MCP Queue Setup"
echo "================================"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ Please don't run this script as root"
   exit 1
fi

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required packages
echo "🔧 Installing dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    docker.io \
    docker-compose \
    bluetooth \
    bluez \
    bluez-tools \
    git \
    curl

# Add user to docker group
echo "👤 Adding user to docker group..."
sudo usermod -aG docker $USER

# Install Python dependencies
echo "🐍 Setting up Python environment..."
python3 -m pip install --user --upgrade pip

# Create data directory
echo "📁 Creating data directory..."
mkdir -p ~/task_printer_data
chmod 755 ~/task_printer_data

# Copy environment file
if [ ! -f .env ]; then
    echo "⚙️ Creating environment configuration..."
    cp .env.example .env
    echo "✏️ Please edit .env file with your printer address:"
    echo "   nano .env"
fi

# Build Docker images
echo "🐳 Building Docker images..."
docker-compose build

# Create systemd service for auto-start
echo "🔄 Creating systemd service..."
sudo tee /etc/systemd/system/task-printer-queue.service > /dev/null <<EOF
[Unit]
Description=Task Printer MCP Queue System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
User=$USER
Group=docker

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable task-printer-queue.service

echo ""
echo "✅ Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env file with your printer Bluetooth address:"
echo "   nano .env"
echo ""
echo "2. Start the services:"
echo "   docker-compose up -d"
echo ""
echo "3. View logs:"
echo "   docker-compose logs -f"
echo ""
echo "4. Test the system:"
echo "   docker-compose exec mcp-server python -c \"from shared.job_queue import JobQueue; q = JobQueue('/app/data/job_queue.db'); print('✅ Queue system ready')\""
echo ""
echo "🔧 The service will auto-start on boot"
echo "🔗 MCP server will be available on port 7210"
echo ""
echo "⚠️  You may need to log out and back in for docker group changes to take effect"