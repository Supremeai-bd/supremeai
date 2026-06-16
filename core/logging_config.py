import sys
from loguru import logger

def setup_logging():
    """
    Configures Loguru for structured logging.
    In production, this could also push to OpenTelemetry.
    """
    logger.remove()
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )
    logger.add(
        "logs/supremeai.log",
        rotation="10 MB",
        retention="10 days",
        compression="zip",
        level="DEBUG",
    )