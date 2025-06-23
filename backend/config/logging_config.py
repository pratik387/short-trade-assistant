import logging
from pathlib import Path
import sys

def setup_logging(log_file: str = "logs/agent.log"):
    Path("logs").mkdir(exist_ok=True)

    # Clear root handlers if already configured
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Console handler (emoji-safe)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)

    # File handler (emoji allowed)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # Attach both
    logging.basicConfig(level=logging.DEBUG, handlers=[console_handler, file_handler])
