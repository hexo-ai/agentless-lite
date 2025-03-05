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


# Add this class after the imports
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
    """
    Set up comprehensive logging that captures ALL logs including those from imported modules
    and redirects them to both console and file.
    
    Args:
        output_dir: Base output directory
        instance_id: Optional instance ID. If None, logs to the base directory
    """
    # Determine log directory and file path
    if instance_id:
        # Instance-specific logging
        instance_dir = os.path.join(output_dir, instance_id)
        os.makedirs(instance_dir, exist_ok=True)
        log_file_path = os.path.join(instance_dir, 'stdout.log')
    else:
        # Base logging
        os.makedirs(output_dir, exist_ok=True)
        log_file_path = os.path.join(output_dir, 'stdout.log')
    
    # Configure root logger to capture everything
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Create a file handler that writes to our log file
    file_handler = logging.FileHandler(log_file_path, mode='a')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Add the handler to the root logger
    root_logger.addHandler(file_handler)
    
    # Create a custom stream handler for stdout/stderr
    class FileWritingStream:
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
    
    # Redirect stdout and stderr to also write to the log file
    sys.stdout = FileWritingStream(sys.__stdout__, log_file_path)
    sys.stderr = FileWritingStream(sys.__stderr__, log_file_path)
    
    # Explicitly capture a_logger (from OpenHands)
    try:
        a_logger.addHandler(file_handler)
    except Exception:
        pass  # In case a_logger isn't available
    
    # Find and capture all existing loggers
    for logger_name in logging.root.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        if logger.handlers:
            # Add our file handler to this logger too
            logger.addHandler(file_handler)
    
    return logging.getLogger('main')  # Return a configured logger


async def main():
    # Set up base output directory
    output_base = Path('swebench_outputs')
    output_base.mkdir(exist_ok=True)
    
    # Set up logging for the main process
    logger = setup_complete_logging(output_base)

    # Load SWE-bench Lite dataset
    dataset = load_dataset('princeton-nlp/SWE-bench_Lite', split='test')
    # Define target instances and their iterations
    target_instances = {
        'django__django-11179': 16,
        'django__django-11039': 34,
        'django__django-14672': 26,
        'django__django-10914': 27,
        'django__django-13401': 26,
        'django__django-12497': 23,
        'django__django-11815': 32,
        'django__django-13230': 30,
        'django__django-11583': 33,
        'django__django-13964': 36,
        'django__django-14017': 33,
        'django__django-12700': 24,
        'django__django-14382': 15,
        'django__django-11620': 28,
        'astropy__astropy-12907': 50,
        'django__django-13757': 25,
        'django__django-13028': 36,
        'django__django-11133': 22,
        'django__django-14411': 24,
        'django__django-13658': 18,
        'django__django-13925': 24,
        'django__django-11001': 56,
        'django__django-12453': 19,
        'django__django-12983': 14,
        'django__django-11099': 17,
        'django__django-14608': 32,
        
        'astropy__astropy-14995' : 10,
        'django__django-11630': 20,
        'django__django-13660': 90,
    }
    
    # Optional target instance ID
    target_instance_id = args.instance_id  # Get from command line args
    
    if target_instance_id:
        # Process single instance if it's in our target list
        if target_instance_id not in target_instances:
            logger.error(f"Instance {target_instance_id} not in target instances list")
            # return
        instance = next((inst for inst in dataset if inst['instance_id'] == target_instance_id), None)
        if not instance:
            logger.error(f"Instance {target_instance_id} not found in dataset")
            return
        instances = [instance]
        logger.info(f"Processing single instance: {target_instance_id}")
    else:
        # Process only target instances
        instances = [inst for inst in dataset if inst['instance_id'] in target_instances]
        logger.info(f"Processing {len(instances)} target instances")

    for instance in instances:
        instance_id = instance['instance_id']
        logger.info(f'\nProcessing {instance_id}...')

        try:
            # Create instance-specific output directory
            instance_output = output_base / instance_id
            if not target_instance_id and instance_output.exists():
                logger.info(f'Instance {instance_id} already processed, skipping...')
                continue
            instance_output.mkdir(exist_ok=True, parents=True)

            # Setup project
            project_dir = await setup_project(instance)

            # Update logging for this instance
            logger = setup_complete_logging(output_base, instance_id)

            # Extract problem description
            problem_desc = f"""
            {instance['problem_statement']}
            """
            logger.info(f'Problem description: {problem_desc}')
            
            patch=''

            # Run fix_bug and capture all output
            logger.info('Starting find_patch...')
            try:
                # Call as regular function
                patch = find_patch(
                    project_dir=str(project_dir),
                    bug_description=problem_desc,
                    instance_id=instance_id
                )
            except Exception as e:
                logger.error(f"Error processing {instance_id}: {str(e)}", exc_info=True)
                patch = ''
            logger.info('find_patch completed. Success: True')

            # Save results
            result = {
                'instance_id': instance_id,
                # 'success': success,
                'patch': patch,
                'model_name_or_path': 'bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0',
                # 'timestamp': datetime.now().isoformat(),
            }

            # Save results as JSON
            with open(instance_output / 'result.json', 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"Saved results to {instance_output / 'result.json'}")

            # Save raw patch first
            with open(instance_output / 'raw_patch.diff', 'w') as f:
                f.write(patch or "")
            logger.info(f"Saved raw patch to {instance_output / 'raw_patch.diff'}")

            # Save clean patch
            clean_patch_text = clean_patch(patch)
            with open(instance_output / 'patch.diff', 'w') as f:
                f.write(clean_patch_text or "")
            logger.info(f"Saved clean patch to {instance_output / 'patch.diff'}")

        except Exception as e:
            logger.error(f'Error processing {instance_id}: {str(e)}', exc_info=True)
            if target_instance_id:  # If processing single instance, stop on error
                raise
            continue

        if target_instance_id:  # If processing single instance, stop after completion
            break

    # Restore original stdout/stderr
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__


def clean_patch(patch_text):
    """
    Clean the patch to only include actual code changes, not just permission changes.
    """
    # Split the patch into individual file diffs
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
    
    # Filter out diffs that only change file permissions
    clean_diffs = []
    for diff in file_diffs:
        # Check if this diff contains actual code changes
        # (not just mode changes from 100644 to 100755)
        lines = diff.splitlines()
        has_content_changes = False
        
        for line in lines:
            # Look for lines that start with + or - but not just mode changes
            if (line.startswith('+') or line.startswith('-')) and not line.startswith('old mode ') and not line.startswith('new mode '):
                has_content_changes = True
                break
        
        # If we found actual changes, keep this diff
        if has_content_changes:
            clean_diffs.append(diff)
    
    return '\n'.join(clean_diffs)


if __name__ == '__main__':
    # Add argument parsing
    import argparse
    parser = argparse.ArgumentParser(description='Process SWE-bench instances')
    parser.add_argument('--instance-id', type=str, help='Specific instance ID to process')
    args = parser.parse_args()
    
    asyncio.run(main())

