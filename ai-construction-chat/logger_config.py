# logger_config.py
import logging
import os
from datetime import datetime
from pathlib import Path

def setup_logging():
    """Setup comprehensive logging system"""
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure logging format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    
    # Setup file handlers
    handlers = [
        logging.FileHandler(logs_dir / 'rag_system.log'),
        logging.FileHandler(logs_dir / 'errors.log'),
        logging.StreamHandler()
    ]
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=handlers
    )
    
    # Setup error-only handler
    error_handler = logging.FileHandler(logs_dir / 'errors.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(log_format))
    
    # Get loggers
    app_logger = logging.getLogger('rag_app')
    db_logger = logging.getLogger('database')
    ocr_logger = logging.getLogger('document_processor')
    
    return app_logger, db_logger, ocr_logger

# Performance monitoring decorator
def monitor_performance(operation_name):
    """Decorator to monitor function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            logger = logging.getLogger('performance')
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"PERF: {operation_name} completed in {execution_time:.2f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"PERF: {operation_name} failed after {execution_time:.2f}s - {str(e)}")
                raise
        return wrapper
    return decorator

def log_search_operation(query, results_count, response_time, workspace="main"):
    """Log search operations for analytics"""
    logger = logging.getLogger('search_analytics')
    logger.info(f"SEARCH: query='{query[:100]}' workspace='{workspace}' results={results_count} time={response_time:.2f}s")

def log_document_operation(operation, file_name, status, details=""):
    """Log document operations"""
    logger = logging.getLogger('document_analytics')
    logger.info(f"DOCUMENT: operation='{operation}' file='{file_name}' status='{status}' details='{details}'")
