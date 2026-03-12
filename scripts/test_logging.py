import logging
import json
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from pcag.core.utils.logging_config import setup_logging, request_id_ctx

def test_logging():
    print("Testing logging configuration...")
    setup_logging("test-service")
    
    logger = logging.getLogger("test_logger")
    
    # Test 1: Basic log
    logger.info("This is a test info message")
    
    # Test 2: Log with context
    token = request_id_ctx.set("req-12345")
    logger.info("This is a request scoped message")
    
    # Test 3: Log with extra fields
    logger.warning("This is a warning", extra={"extra_fields": {"user_id": "u-999", "action": "login"}})
    
    # Test 4: Exception
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error("Math error", exc_info=True)
        
    request_id_ctx.reset(token)
    logger.info("Context cleared")

if __name__ == "__main__":
    test_logging()
