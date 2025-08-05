#!/usr/bin/env python3
"""
Printing Service for Task Printer Queue System
Polls the job queue and prints tasks to the thermal printer
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add shared directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from job_queue import JobQueue, PrintJob, JobStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TaskCardPrinter:
    """Handles the actual printing of task cards"""
    
    def __init__(self, printer_address: str = None):
        self.printer_address = printer_address or os.getenv('PRINTER_ADDRESS', 'AA56CEF0-AA49-FD9B-0331-2C91D3622AA9')
        self.simulation_mode = os.getenv('SIMULATION_MODE', 'false').lower() == 'true'
        
        if self.simulation_mode:
            logger.info("🧪 Running in SIMULATION MODE - no actual printing")
        else:
            logger.info(f"🖨️ Printer configured: {self.printer_address}")
    
    async def print_task_card(self, job: PrintJob) -> bool:
        """Print a task card to the thermal printer"""
        try:
            if self.simulation_mode:
                return await self._simulate_print(job)
            else:
                return await self._actual_print(job)
                
        except Exception as e:
            logger.error(f"❌ Print error for job {job.job_id}: {e}")
            return False
    
    async def _simulate_print(self, job: PrintJob) -> bool:
        """Simulate printing for testing purposes"""
        logger.info(f"🧪 SIMULATING print job {job.job_id}: {job.title}")
        
        # Simulate different print times based on priority
        print_times = {'high': 2, 'medium': 3, 'low': 4}
        print_time = print_times.get(job.priority, 3)
        
        logger.info(f"📝 Printing card for: {job.title}")
        logger.info(f"🚦 Priority: {job.priority} | 📁 Category: {job.category}")
        if job.description:
            logger.info(f"📄 Description: {job.description[:50]}...")
        if job.estimated_time:
            logger.info(f"⏱️ Estimated time: {job.estimated_time}")
        
        # Simulate printing delay
        await asyncio.sleep(print_time)
        
        logger.info(f"✅ SIMULATION complete for job {job.job_id}")
        return True
    
    async def _actual_print(self, job: PrintJob) -> bool:
        """Actually print to the thermal printer"""
        logger.info(f"🖨️ Printing job {job.job_id}: {job.title}")
        
        try:
            # Import thermal printer modules
            from fixed_main import LuckPrinter, BluetoothDevice
            from image_card_designer import ImageCardDesigner
            
            # Create printer connection
            device = BluetoothDevice(self.printer_address)
            printer = LuckPrinter(device)
            
            # Create card designer
            card_designer = ImageCardDesigner(width=384, font_path="zpix.ttf")
            
            # Connect to printer
            logger.info(f"🔗 Connecting to printer...")
            await printer.initialize()
            
            # Generate task card image
            logger.info(f"🎨 Generating task card...")
            task_data = self._job_to_task_data(job)
            card_image = card_designer.create_task_card(task_data)
            
            # Print the card
            logger.info(f"🖨️ Printing task card...")
            await printer.print_image(card_image)
            await printer.print_end()
            
            logger.info(f"✅ Successfully printed job {job.job_id}")
            return True
            
        except ImportError as e:
            logger.error(f"❌ Missing printer modules: {e}")
            logger.error("💡 Make sure thermal printer code is available")
            return False
            
        except Exception as e:
            logger.error(f"❌ Print error for job {job.job_id}: {e}")
            return False
            
        finally:
            try:
                await printer.close()
            except:
                pass
    
    def _job_to_task_data(self, job: PrintJob):
        """Convert print job to task data format for card designer"""
        from printer_models import TaskPrintRequest, Priority, TaskCategory
        
        # Convert string priority to enum
        priority_map = {'high': Priority.HIGH, 'medium': Priority.MEDIUM, 'low': Priority.LOW}
        priority = priority_map.get(job.priority, Priority.MEDIUM)
        
        # Convert string category to enum
        category_map = {
            'work': TaskCategory.WORK,
            'personal': TaskCategory.PERSONAL, 
            'urgent': TaskCategory.URGENT,
            'learning': TaskCategory.LEARNING,
            'health': TaskCategory.HEALTH,
            'other': TaskCategory.OTHER
        }
        category = category_map.get(job.category, TaskCategory.OTHER)
        
        return TaskPrintRequest(
            title=job.title,
            description=job.description or '',
            priority=priority,
            category=category,
            estimated_time=job.estimated_time or '',
            due_date=job.due_date,
            task_id=job.job_id[:8].upper()
        )

class PrintingService:
    """Main printing service that polls the queue and processes jobs"""
    
    def __init__(self, db_path: str = None, poll_interval: int = 5):
        self.db_path = db_path or os.getenv("DB_PATH", "./data/job_queue.db")
        self.poll_interval = poll_interval
        self.job_queue = JobQueue(self.db_path)
        self.printer = TaskCardPrinter()
        self.running = False
        
        logger.info(f"📂 Database: {self.db_path}")
        logger.info(f"⏰ Poll interval: {poll_interval} seconds")
    
    async def start(self):
        """Start the printing service"""
        self.running = True
        logger.info("🚀 Starting Task Printer Service...")
        
        # Ensure database directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Print startup stats
        stats = self.job_queue.get_queue_stats()
        pending_jobs = stats.get('pending', 0) + stats.get('retry', 0)
        logger.info(f"📊 Queue status: {pending_jobs} jobs waiting, {stats.get('completed', 0)} completed")
        
        while self.running:
            try:
                await self._process_next_job()
                await asyncio.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                logger.info("⏹️ Stopping printing service...")
                self.running = False
                break
                
            except Exception as e:
                logger.error(f"❌ Service error: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _process_next_job(self):
        """Process the next job in the queue"""
        # Get next job
        job = self.job_queue.get_next_job()
        if not job:
            return  # No jobs to process
        
        logger.info(f"📥 Processing job {job.job_id}: {job.title}")
        
        # Update status to processing
        self.job_queue.update_job_status(job.job_id, JobStatus.PROCESSING)
        
        try:
            # Attempt to print
            success = await self.printer.print_task_card(job)
            
            if success:
                # Mark as completed
                self.job_queue.update_job_status(job.job_id, JobStatus.COMPLETED)
                logger.info(f"✅ Job {job.job_id} completed successfully")
                
            else:
                # Handle failure - retry or mark as failed
                if self.job_queue.increment_retry_count(job.job_id):
                    logger.warning(f"🔄 Job {job.job_id} queued for retry")
                else:
                    logger.error(f"❌ Job {job.job_id} failed permanently")
        
        except Exception as e:
            logger.error(f"❌ Error processing job {job.job_id}: {e}")
            
            # Handle error - retry or mark as failed
            error_message = f"Processing error: {str(e)}"
            if self.job_queue.increment_retry_count(job.job_id):
                self.job_queue.update_job_status(job.job_id, JobStatus.RETRY, error_message)
                logger.warning(f"🔄 Job {job.job_id} queued for retry due to error")
            else:
                self.job_queue.update_job_status(job.job_id, JobStatus.FAILED, error_message)
                logger.error(f"❌ Job {job.job_id} failed permanently")
    
    def stop(self):
        """Stop the printing service"""
        self.running = False
        logger.info("⏹️ Printing service stopped")

class ServiceManager:
    """Manages the printing service with health monitoring"""
    
    def __init__(self):
        self.service = PrintingService()
        self.last_cleanup = datetime.now()
        self.cleanup_interval = 24 * 60 * 60  # 24 hours
    
    async def run(self):
        """Run the service with health monitoring"""
        logger.info("🏥 Starting Service Manager...")
        
        # Start main service
        service_task = asyncio.create_task(self.service.start())
        
        # Start health monitoring
        health_task = asyncio.create_task(self._health_monitor())
        
        try:
            await asyncio.gather(service_task, health_task)
        except KeyboardInterrupt:
            logger.info("⏹️ Service Manager shutting down...")
            self.service.stop()
    
    async def _health_monitor(self):
        """Monitor service health and perform maintenance"""
        while self.service.running:
            try:
                # Check if cleanup is needed
                now = datetime.now()
                if (now - self.last_cleanup).total_seconds() > self.cleanup_interval:
                    logger.info("🧹 Running database cleanup...")
                    deleted = self.service.job_queue.cleanup_old_jobs(days=7)
                    logger.info(f"🗑️ Cleaned up {deleted} old jobs")
                    self.last_cleanup = now
                
                # Log stats periodically
                stats = self.service.job_queue.get_queue_stats()
                pending = stats.get('pending', 0) + stats.get('retry', 0)
                
                if pending > 0:
                    logger.info(f"📊 Health: {pending} jobs pending, {stats.get('processing', 0)} processing")
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"❌ Health monitor error: {e}")
                await asyncio.sleep(60)

async def main():
    """Main entry point"""
    logger.info("🖨️ Task Printer Service Starting...")
    
    # Print configuration
    logger.info(f"🔧 Configuration:")
    logger.info(f"   DB Path: {os.getenv('DB_PATH', './data/job_queue.db')}")
    logger.info(f"   Printer: {os.getenv('PRINTER_ADDRESS', 'AA56CEF0-AA49-FD9B-0331-2C91D3622AA9')}")
    logger.info(f"   Simulation: {os.getenv('SIMULATION_MODE', 'false')}")
    
    # Start service manager
    manager = ServiceManager()
    await manager.run()

if __name__ == "__main__":
    asyncio.run(main())