from termcolor import colored
import re
import logging
from typing import Any

# Remove the root logger handlers to prevent duplicate logging
logging.getLogger().handlers = []

class ColoredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        # Clear any existing handlers
        self.logger.handlers = []
        
        # Create console handler with formatting
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s | %(message)s', datefmt='%H:%M:%S')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        
        # Prevent propagation to avoid duplicate logging
        self.logger.propagate = False
    
    def info(self, msg, color='green', **kwargs):
        self.logger.info(colored(msg, color))
    
    def error(self, msg, **kwargs):
        self.logger.error(colored(msg, 'red', attrs=['bold']))
    
    def warning(self, msg, **kwargs):
        self.logger.warning(colored(msg, 'yellow'))
    
    def action(self, msg, **kwargs):
        self.logger.info(colored(f"[ACTION] {msg}", 'cyan'))
    
    def observation(self, msg, **kwargs):
        # Format the message for better readability if it's a TextContent object
        if hasattr(msg, 'text') and hasattr(msg, 'type'):
            # It's likely a TextContent object
            formatted_msg = msg.text
        elif isinstance(msg, str):
            formatted_msg = msg
        else:
            # Try to convert to string in a readable way
            formatted_msg = str(msg)
            
        # Clean up the message to make it more readable
        formatted_msg = formatted_msg.replace('\\n', '\n')  # Replace escaped newlines
        formatted_msg = re.sub(r'\[TextContent\(.*?\)\]', '', formatted_msg)  # Remove TextContent wrappers
        
        self.logger.info(colored(f"[OBSERVATION] {formatted_msg}", 'magenta'))
    
    def debug(self, msg, **kwargs):
        self.logger.debug(colored(msg, 'blue'))

    def llm_request(self, prompt: str, **kwargs):
        """Log LLM request with formatted prompt"""
        self.logger.info("\n" + colored("=== LLM REQUEST ===", 'cyan', attrs=['bold']))
        self.logger.info(colored("Prompt:", 'cyan'))
        self.logger.info(colored(f"{prompt}", 'white'))
        if kwargs:
            self.logger.info(colored("Parameters:", 'cyan'))
            for k, v in kwargs.items():
                self.logger.info(colored(f"  {k}: {v}", 'white'))
        self.logger.info(colored("==================\n", 'cyan', attrs=['bold']))

    def llm_response(self, response: str, parsed_result: Any = None):
        """Log LLM response with optional parsed result"""
        self.logger.info("\n" + colored("=== LLM RESPONSE ===", 'green', attrs=['bold']))
        self.logger.info(colored("Raw Response:", 'green'))
        self.logger.info(colored(f"{response}", 'white'))
        if parsed_result is not None:
            self.logger.info(colored("Parsed Result:", 'green'))
            self.logger.info(colored(f"{parsed_result}", 'white'))
        self.logger.info(colored("===================\n", 'green', attrs=['bold']))

    def step_start(self, step_name: str):
        """Log the start of a processing step"""
        self.logger.info("\n" + colored(f"▶ Starting: {step_name}", 'blue', attrs=['bold']))

    def step_end(self, step_name: str, result: Any = None):
        """Log the end of a processing step"""
        self.logger.info(colored(f"✓ Completed: {step_name}", 'blue', attrs=['bold']))
        if result:
            self.logger.info(colored("Result:", 'blue'))
            self.logger.info(colored(f"{result}", 'white'))
        self.logger.info("")

# Create a single global logger instance
logger = ColoredLogger('SWE-Agent')
