#!/usr/bin/env python3.12
import argparse
import contextlib
import logging
import os
import sys
import time
import subprocess

# Configure logging with debug support
def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure logging based on debug flag."""
    log_level: int = logging.DEBUG if debug else logging.INFO
    
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    
    return logger

logger: logging.Logger | None = None

# Auto-detect log file path
LOG_PATH: str = os.path.expanduser('~/.parsec/log.txt')
if not os.path.exists(LOG_PATH) and os.path.exists('/Users/Shared/.parsec/log.txt'):
    LOG_PATH = '/Users/Shared/.parsec/log.txt'

# Auto-detect log file path
LOG_PATH = os.path.expanduser('~/.parsec/log.txt')
if not os.path.exists(LOG_PATH) and os.path.exists('/Users/Shared/.parsec/log.txt'):
    LOG_PATH = '/Users/Shared/.parsec/log.txt'

def set_karabiner_var(is_active):
    """Set Karabiner-Elements variable for Parsec guest status."""
    logger.debug(f"set_karabiner_var called with is_active={is_active}")
    val = 1 if is_active else 0
    cmd = [
        "/Library/Application Support/org.pqrs/Karabiner-Elements/bin/karabiner_cli",
        "--set-variables",
        f'{{"parsec_guest_active": {val}}}'
    ]
    logger.debug(f"Executing Karabiner CLI command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logger.debug(f"Karabiner CLI returned: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Karabiner CLI failed with return code {e.returncode}: {e.stderr.strip()}")
    except Exception as e:
        logger.error(f"Unexpected error in set_karabiner_var: {e}")

def follow(filepath: str):
    """Generates new lines appended to the file, handling file rotation/recreation."""
    logger.debug(f"follow() started monitoring filepath: {filepath}")
    while True:
        try:
            with open(filepath, 'r', errors='ignore') as f:
                # Go to end of file to ignore historical logs
                f.seek(0, os.SEEK_END)
                current_size = f.tell()
                logger.debug(f"Opened {filepath}, seeking to end (size: {current_size})")
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.5)
                        # Re-open if Parsec truncates, rotates, or deletes the log
                        if os.path.exists(filepath):
                            current_size = os.path.getsize(filepath)
                            pos = f.tell()
                            logger.debug(f"File size check: {current_size} < {pos}? {current_size < pos}")
                            if current_size < pos:
                                logger.debug(f"File truncated/rotated, resetting position")
                                break
                        else:
                            logger.warning(f"Log file {filepath} does not exist")
                            break
                        continue
                    logger.debug(f"Yielding line: {line.strip()}")
                    yield line
        except FileNotFoundError as e:
            logger.warning(f"FileNotFoundError for {filepath}: {e}")
            time.sleep(2)
        except PermissionError as e:
            logger.error(f"PermissionError for {filepath}: {e}")
            time.sleep(2)
        except OSError as e:
            logger.error(f"OSError while monitoring {filepath}: {e}")
            time.sleep(2)

def main():
    """Main entry point for Parsec guest monitor."""
    logger.info("Parsec Guest Monitor starting...")
    
    # Initialize Karabiner variable to inactive on script startup
    current_state: bool = False
    logger.debug(f"Initial state: current_state={current_state}")
    set_karabiner_var(current_state)

    # Monitor new incoming logs
    logger.info(f"Monitoring log file: {LOG_PATH}")
    for line in follow(LOG_PATH):
        stripped_line: str = line.strip()
        
        # Check for connection events
        is_connected_event = "connected." in stripped_line
        is_disconnected_event = (
            "disconnected." in stripped_line or
            "Connection closed" in stripped_line or
            "kick" in stripped_line
        )
        
        if not is_connected_event and not is_disconnected_event:
            continue
        
        # Handle connection event
        if is_connected_event:
            if current_state:
                continue
            
            logger.info("Parsec connected - activating Karabiner variable")
            current_state = True
            set_karabiner_var(current_state)
            continue
        
        # Handle disconnection event
        if is_disconnected_event:
            if not current_state:
                continue
            
            logger.info("Parsec disconnected - deactivating Karabiner variable")
            current_state = False
            set_karabiner_var(current_state)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Monitor Parsec connection status and control Karabiner-Elements variable"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging mode"
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    logger = setup_logging(debug=args.debug)
    main()
