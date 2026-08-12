"""
Centralized logging system
All modules use this for consistent logging
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name="SchemaVaultLocal", level=logging.INFO):
    """
    Setup logger with file and console handlers
    
    Each module gets its own named logger instance, but they all
    write to the same log file for centralized debugging.
    
    Args:
        name: Logger name (typically module name)
        level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """
    
    # Create logs directory
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger
    
    # File handler - all logs go to daily file
    log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler - show INFO and above in console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Formatter with timestamp, logger name, level, and message
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger