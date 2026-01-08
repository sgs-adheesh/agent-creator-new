"""
Logging configuration for the application
"""
import logging
import sys
from pathlib import Path
from typing import Optional

# Create logs directory if it doesn't exist
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Track if logging has been initialized to prevent double initialization
_logging_initialized = False

# Configure root logger
def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None, force: bool = False):
    """
    Setup logging configuration for the application
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path (default: logs/app.log)
        force: If True, reinitialize even if already initialized (default: False)
    
    Returns:
        Root logger instance
    """
    global _logging_initialized
    
    # Prevent double initialization unless forced
    if _logging_initialized and not force:
        return logging.getLogger()
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Default log file
    if log_file is None:
        log_file = LOG_DIR / "app.log"
    else:
        log_file = Path(log_file)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers only if forcing reinitialization
    if force or not _logging_initialized:
        root_logger.handlers.clear()
    
    # Console handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (DEBUG and above)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Mark as initialized
    _logging_initialized = True
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def is_logging_initialized() -> bool:
    """
    Check if logging has been initialized
    
    Returns:
        True if logging has been initialized, False otherwise
    """
    return _logging_initialized
