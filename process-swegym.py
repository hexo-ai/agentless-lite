import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
import logging.handlers
import re

from datasets import load_dataset

from main import find_patch, logger as a_logger

# Add the TeeStream class
class TeeStream:
    def __init__(self, original_stream, log_file_path):
        self.original_stream = original_stream
        self.log_file_path = log_file_path
        
    def write(self, data):
        self.original_stream.write(data)
        with open(self.log_file_path, 'a') as f:
            f.write(data)
            
    def flush(self):
        self.original_stream.flush()
        
    def isatty(self):
        return hasattr(self.original_stream, 'isatty') and self.original_stream.isatty()

# Add the StreamTee class
class StreamTee:
    def __init__(self, stream1, stream2):
        self.stream1 = stream1
        self.stream2 = stream2
        
    def write(self, data):
        self.stream1.write(data)
        self.stream2.write(data)
        
    def flush(self):
        self.stream1.flush()
        self.stream2.flush()
        
    def isatty(self):
        return hasattr(self.stream1, 'isatty') and self.stream1.isatty()

# Add the LogCapture class
class LogCapture:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        self.terminal_stdout = sys.stdout
        self.terminal_stderr = sys.stderr
        self.log_file = None
        
    def __enter__(self):
        # Open the log file
        self.log_file = open(self.log_file_path, 'a', buffering=1)  # Line buffering
        
        # Create custom stdout/stderr redirectors
        sys.stdout = StreamTee(self.terminal_stdout, self.log_file)
        sys.stderr = StreamTee(self.terminal_stderr, self.log_file)
        
        # Configure root logger to capture all logs
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove any existing handlers to avoid duplication
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        root_logger.addHandler(console_handler)
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original stdout/stderr
        sys.stdout = self.terminal_stdout
        sys.stderr = self.terminal_stderr
        
        # Close log file
        if self.log_file:
            self.log_file.close()

# Add the LogTee class
class LogTee:
    def __init__(self, stream1, stream2):
        self.stream1 = stream1
        self.stream2 = stream2
        
    def write(self, data):
        self.stream1.write(data)
        self.stream2.write(data)
        
    def flush(self):
        self.stream1.flush()
        self.stream2.flush()
        
    def isatty(self):
        return hasattr(self.stream1, 'isatty') and self.stream1.isatty()

# Add the AllLogsCapture class (this is the most comprehensive one)
class AllLogsCapture:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        self.terminal_stdout = sys.stdout
        self.terminal_stderr = sys.stderr
        self.log_file = None
        self.original_handlers = {}
        
    def __enter__(self):
        # Open the log file
        self.log_file = open(self.log_file_path, 'a', buffering=1)  # Line buffering
        
        # Create custom stdout/stderr redirectors
        sys.stdout = LogTee(self.terminal_stdout, self.log_file)
        sys.stderr = LogTee(self.terminal_stderr, self.log_file)
        
        # Save all existing loggers and their handlers
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            if logger.handlers:
                self.original_handlers[logger_name] = list(logger.handlers)
                
                # Add a handler that writes to our log file
                file_handler = logging.FileHandler(self.log_file_path)
                file_handler.setFormatter(logging.Formatter('%(message)s'))
                logger.addHandler(file_handler)
        
        # Configure root logger
        root_logger = logging.getLogger()
        if root_logger.handlers:
            self.original_handlers['root'] = list(root_logger.handlers)
        
        # Add file handler to root logger
        file_handler = logging.FileHandler(self.log_file_path)
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        root_logger.addHandler(file_handler)
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original stdout/stderr
        sys.stdout = self.terminal_stdout
        sys.stderr = self.terminal_stderr
        
        # Restore original logger handlers
        for logger_name, handlers in self.original_handlers.items():
            if logger_name == 'root':
                logger = logging.getLogger()
            else:
                logger = logging.getLogger(logger_name)
                
            # Remove all handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
                
            # Restore original handlers
            for handler in handlers:
                logger.addHandler(handler)
        
        # Close log file
        if self.log_file:
            self.log_file.close()

async def setup_project(instance):
    """Setup project directory and checkout correct commit"""
    repo_name = instance['repo'].replace('/', '__')
    project_dir = Path(f'projects/{repo_name}')

    # Clone repo if not exists
    if not project_dir.exists():
        os.makedirs(project_dir.parent, exist_ok=True)
        clone_url = f"https://github.com/{instance['repo']}.git"
        subprocess.run(['git', 'clone', clone_url, str(project_dir)], check=True)

    # Checkout the base commit
    result = subprocess.run(
        ['git', 'checkout', '-f', instance['base_commit']],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    logging.info(
        f'Git checkout output:\nstdout: {result.stdout}\nstderr: {result.stderr}'
    )

    return project_dir

def setup_complete_logging(output_dir, instance_id=None):
    """Set up comprehensive logging that captures ALL logs"""
    if instance_id:
        instance_dir = os.path.join(output_dir, instance_id)
        os.makedirs(instance_dir, exist_ok=True)
        log_file_path = os.path.join(instance_dir, 'stdout.log')
    else:
        os.makedirs(output_dir, exist_ok=True)
        log_file_path = os.path.join(output_dir, 'stdout.log')
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    file_handler = logging.FileHandler(log_file_path, mode='a')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(file_handler)
    
    return logging.getLogger('main')

async def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Process swegym instances')
    parser.add_argument('--instance-id', type=str, help='Specific instance ID to process')
    parser.add_argument('--n', type=int, default=None, help='Limit processing to first N instances')
    args = parser.parse_args()
    
    # Set up base output directory
    output_base = 'swegym_outputs'
    os.makedirs(output_base, exist_ok=True)
    
    # Determine instance ID and log file path
    instance_id = args.instance_id
    n = args.n
    
    if instance_id:
        # Instance-specific logging
        instance_dir = os.path.join(output_base, instance_id)
        os.makedirs(instance_dir, exist_ok=True)
        log_file_path = os.path.join(instance_dir, 'stdout.log')
    else:
        # Fallback to a default log if no instance ID provided
        log_file_path = os.path.join(output_base, 'default_stdout.log')
    
    # Use the AllLogsCapture context manager to handle logging
    with AllLogsCapture(log_file_path):
        logging.info(f"Processing {'single instance: ' + instance_id if instance_id else 'instances'}")
        
        # Load SWE-Gym dataset
        dataset = load_dataset("SWE-Gym/SWE-Gym-Lite")['train']  # Assuming we want the train split
        
        if instance_id:
            # Process single instance
            instance = next((inst for inst in dataset if inst['instance_id'] == instance_id), None)
            if not instance:
                logging.error(f"Instance {instance_id} not found in dataset")
                return
            instances = [instance]
            logging.info(f"Processing single instance: {instance_id}")
        else:
            # Process instances with optional limit
            instances = dataset
            if n is not None:
                instances = list(instances)[:n]  # Convert to list before slicing
                logging.info(f"Processing first {n} instances")
            else:
                logging.info(f"Processing all instances")

        for instance in instances:
            # Make sure instance is a dictionary before accessing it
            if not isinstance(instance, dict):
                logging.error(f"Invalid instance format: {instance}")
                continue
                
            instance_id = instance['instance_id']
            logging.info(f'\nProcessing {instance_id}...')

            try:
                # Create instance-specific output directory
                instance_output = os.path.join(output_base, instance_id)
                if not instance_id and os.path.exists(instance_output):
                    logging.info(f'Instance {instance_id} already processed, skipping...')
                    continue
                os.makedirs(instance_output, exist_ok=True)

                # Setup project
                project_dir = await setup_project(instance)

                # Update logging for this instance
                logger = setup_complete_logging(output_base, instance_id)

                # Extract problem description and hints
                problem_desc = f"""
                {instance['problem_statement']}
                
                Additional Hints:
                {instance['hints_text']}
                """
                logger.info(f'Problem description: {problem_desc}')
                
                patch = ''

                # Run fix_bug and capture all output
                logger.info('Starting find_patch...')
                try:
                    patch = find_patch(
                        project_dir=str(project_dir),
                        bug_description=problem_desc,
                    )
                except Exception as e:
                    logger.error(f"Error processing {instance_id}: {str(e)}", exc_info=True)
                    patch = ''
                logger.info('find_patch completed')

                # Save results
                result = {
                    'instance_id': instance_id,
                    'patch': patch,
                    'model_name_or_path': 'bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0',
                    'original_patch': instance['patch'],
                    'test_patch': instance['test_patch'],
                    'created_at': instance['created_at'],
                    'version': instance['version']
                }

                # Save results as JSON
                with open(os.path.join(instance_output, 'result.json'), 'w') as f:
                    json.dump(result, f, indent=2)
                logger.info(f"Saved results to {os.path.join(instance_output, 'result.json')}")

                # Save raw patch first
                with open(os.path.join(instance_output, 'raw_patch.diff'), 'w') as f:
                    f.write(patch)
                logger.info(f"Saved raw patch to {os.path.join(instance_output, 'raw_patch.diff')}")

                # Save clean patch
                clean_patch_text = clean_patch(patch)
                with open(os.path.join(instance_output, 'patch.diff'), 'w') as f:
                    f.write(clean_patch_text)
                logger.info(f"Saved clean patch to {os.path.join(instance_output, 'patch.diff')}")

            except Exception as e:
                logging.error(f'Error processing {instance_id}: {str(e)}', exc_info=True)
                if instance_id:  # If processing single instance, stop on error
                    raise
                continue


    # Restore original stdout/stderr
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

def clean_patch(patch_text):
    """Clean the patch to only include actual code changes"""
    file_diffs = []
    current_diff = []
    
    for line in patch_text.splitlines():
        if line.startswith('diff --git '):
            if current_diff:
                file_diffs.append('\n'.join(current_diff))
                current_diff = []
            current_diff.append(line)
        elif current_diff:
            current_diff.append(line)
    
    if current_diff:
        file_diffs.append('\n'.join(current_diff))
    
    clean_diffs = []
    for diff in file_diffs:
        lines = diff.splitlines()
        has_content_changes = False
        
        for line in lines:
            if (line.startswith('+') or line.startswith('-')) and not line.startswith('old mode ') and not line.startswith('new mode '):
                has_content_changes = True
                break
        
        if has_content_changes:
            clean_diffs.append(diff)
    
    return '\n'.join(clean_diffs)

if __name__ == '__main__':
    asyncio.run(main())