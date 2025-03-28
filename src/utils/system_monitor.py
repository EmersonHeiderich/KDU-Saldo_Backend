# src/utils/system_monitor.py
# Utility functions for logging system resource usage.

import os
import psutil
import threading
import time
from typing import Optional # <<<--- ADD THIS IMPORT
from .logger import logger # Import the configured application logger

_monitor_thread: Optional[threading.Thread] = None
_stop_monitor = threading.Event()

def log_system_resources():
    """Logs information about current system resource usage (Memory, CPU, Threads, etc.)."""
    try:
        process = psutil.Process(os.getpid())

        # Memory Usage (RSS - Resident Set Size)
        memory_info = process.memory_info()
        mem_mb = memory_info.rss / (1024 * 1024)
        logger.info(f"Resource Usage - Memory (RSS): {mem_mb:.2f} MB")

        # CPU Usage
        # cpu_percent() blocks for the specified interval. Use 0.1 for a quick check.
        # Using interval=None gives usage since last call, which can be less intuitive for periodic checks.
        cpu_percent = process.cpu_percent(interval=0.1)
        logger.info(f"Resource Usage - CPU: {cpu_percent:.2f}%")

        # Number of Threads
        threads = process.num_threads()
        logger.info(f"Resource Usage - Threads: {threads}")

        # File Descriptors (Platform dependent)
        try:
            open_files = len(process.open_files())
            logger.info(f"Resource Usage - Open Files: {open_files}")
        except (psutil.AccessDenied, NotImplementedError, Exception) as e:
            # May fail on some OS or without sufficient permissions
            logger.debug(f"Could not get open files count: {type(e).__name__}")

        # Network Connections (Platform dependent)
        try:
            connections = len(process.connections(kind='inet')) # Filter for internet connections
            logger.info(f"Resource Usage - Network Connections (inet): {connections}")
        except (psutil.AccessDenied, NotImplementedError, Exception) as e:
            # May fail on some OS or without sufficient permissions
            logger.debug(f"Could not get network connections count: {type(e).__name__}")

    except psutil.NoSuchProcess:
         logger.warning("Could not get process info for resource monitoring (process ended?).")
    except Exception as e:
        logger.error(f"Error logging system resources: {e}", exc_info=True)


def _monitor_task(interval_seconds: int = 300):
    """The background task that periodically logs resources."""
    logger.info(f"Starting periodic resource monitor (Interval: {interval_seconds}s)")
    while not _stop_monitor.is_set():
         log_system_resources()
         # Wait for the specified interval or until stop event is set
         _stop_monitor.wait(timeout=interval_seconds)
    logger.info("Periodic resource monitor stopped.")


def start_resource_monitor(interval_seconds: int = 300):
    """
    Starts the background thread for periodic resource monitoring.
    Ensures only one monitor thread is running.

    Args:
        interval_seconds: How often to log resources (in seconds). Default is 5 minutes.
    """
    global _monitor_thread
    if _monitor_thread is None or not _monitor_thread.is_alive():
        _stop_monitor.clear() # Ensure stop flag is reset
        _monitor_thread = threading.Thread(target=_monitor_task, args=(interval_seconds,), daemon=True)
        _monitor_thread.start()
    else:
         logger.debug("Resource monitor thread already running.")


def stop_resource_monitor():
    """Signals the background monitor thread to stop."""
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        logger.info("Stopping resource monitor thread...")
        _stop_monitor.set()
        _monitor_thread.join(timeout=5) # Wait briefly for thread to finish
        if _monitor_thread.is_alive():
             logger.warning("Resource monitor thread did not stop gracefully.")
        _monitor_thread = None
    else:
         logger.debug("Resource monitor thread not running or already stopped.")