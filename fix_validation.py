import os
import re
import tempfile
import shutil
import subprocess
from typing import Dict, List
from llm import LLMInterface

from logger import logger
from utils import save_llm_response


def generate_tests(llm: LLMInterface, problem_statement: str, repo_path: str, output_dir: str) -> Dict:
    """Generate test cases for the bug fix."""
    test_prompt = f"""
We are currently solving the following issue within our repository. Here is the issue text:
--- BEGIN ISSUE ---
{problem_statement}
--- END ISSUE ---

Please generate a complete test that can be used to reproduce the issue.

The complete test should contain the following:
1. Necessary imports
2. Code to reproduce the issue described in the issue text
3. Print "Issue reproduced" if the outcome indicates that the issue is reproduced
4. Print "Issue resolved" if the outcome indicates that the issue has been successfully resolved
5. Print "Other issues" if the outcome indicates there are other issues with the source code

Here is an example:

```python
from sqlfluff import lint

def test__rules__std_L060_raised() -> None:
    try:
        sql = "SELECT   IFNULL(NULL, 100),
            NVL(NULL,100);"
        result = lint(sql, rules=["L060"])
        assert len(result) == 2
    except:
        print("Other issues")
        return

    try:
        assert result[0]["description"] == "Use 'COALESCE' instead of 'IFNULL'."
        assert result[1]["description"] == "Use 'COALESCE' instead of 'NVL'."
        print("Issue resolved")
    except AssertionError:
        print("Issue reproduced")
        return

    return

test__rules__std_L060_raised()
```

Please ensure the generated test reflects the issue described in the provided issue text.
The generated test should be able to be used to both reproduce the issue as well as to verify the issue has been fixed.
Wrap the complete test in ```python...```.
"""
    
    response = llm.call_llm(test_prompt)
    save_llm_response(
        output_dir=output_dir,
        stage= "test_generation",
        response= response,
        details="test code"
    )
    
    try:
        test_code = response.split('```python')[1].split('```')[0].strip()

        return {
            "test_code": test_code,
            "problem_statement": problem_statement
        }
    except Exception:
        logger.error("Failed to parse test code from LLM response")
        return {
            "test_code": "",
            "problem_statement": problem_statement
        }

def apply_patch_directly(file_path: str, hunks: List[Dict]) -> bool:
    """Apply patch hunks directly by replacing lines in the file"""
    try:
        # Read all lines from the file
        with open(file_path, 'r') as f:
            lines = f.readlines()

        # Apply each hunk
        for hunk in hunks:
            if hunk['start'] is not None:
                # Use the explicit line number from SEARCH block
                start = hunk['start'] - 1  # Convert to 0-based index
                
                # Get the search content and normalize it
                search_content = ''.join(hunk['old']).strip()
                
                # Look for content in a window around the specified line
                window_start = max(0, start - 2)
                window_end = min(len(lines), start + len(hunk['old']) + 2)
                
                # Try to find the exact content within the window
                found = False
                for i in range(window_start, window_end - len(hunk['old']) + 1):
                    window_content = ''.join(lines[i:i + len(hunk['old'])]).strip()
                    if window_content == search_content:
                        start = i
                        found = True
                        break
                
                if not found:
                    logger.error(f"Could not find matching content around line {start+1} in {file_path}")
                    return False
            else:
                # Fall back to content-based search
                search_content = ''.join(hunk['old']).strip()
                file_content = ''.join(lines)
                try:
                    pos = file_content.index(search_content)
                    start = file_content[:pos].count('\n')
                except ValueError:
                    logger.error(f"Could not find matching content in {file_path}")
                    return False

            # Replace the lines
            lines[start:start + len(hunk['old'])] = hunk['new']

        # Write back to file
        with open(file_path, 'w', newline='\n') as f:
            f.writelines(lines)
            
        return True
        
    except Exception as e:
        logger.error(f"Error applying patch directly: {str(e)}")
        return False

def parse_patch_hunks(patch_content: str) -> Dict[str, List[Dict]]:
    """Parse patch content into a dict of file paths and their hunks"""
    files = {}
    current_file = None
    current_hunk = None
    
    # Extract file path and search/replace blocks
    for block in patch_content.split('```python'):
        if not block.strip():
            continue
            
        lines = block.split('\n')
        for line in lines:
            if line.startswith('### '):
                current_file = line[4:].strip()
                files[current_file] = []
            elif '<<<<<<< SEARCH' in line:
                # Extract line numbers if present
                line_nums = re.search(r'\(line (\d+)-(\d+)\)', line)
                if line_nums:
                    start_line = int(line_nums.group(1))
                else:
                    start_line = None
                    
                current_hunk = {
                    'start': start_line,
                    'old': [],
                    'new': []
                }
                # Collect old lines until =======
                in_old = True
            elif line == '=======' and current_hunk is not None:
                in_old = False
            elif line.startswith('>>>>>>> REPLACE'):
                if current_hunk is not None:
                    files[current_file].append(current_hunk)
                current_hunk = None
            elif current_hunk is not None:
                if line.strip():  # Skip empty lines
                    if in_old:
                        current_hunk['old'].append(line + '\n')
                    else:
                        current_hunk['new'].append(line + '\n')
    
    return files

def validate_fixes(repo_path: str, fixes: List[Dict], tests: Dict, output_dir: str) -> tuple[List[Dict], str]:
    """Validate generated fixes using the test cases and return fixes with a consolidated git diff."""
    logger.step_start("Validating Fixes")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_copy = os.path.join(temp_dir, 'repo')
        shutil.copytree(repo_path, repo_copy)
        
        # Initialize git repository if not exists
        if not os.path.exists(os.path.join(repo_copy, '.git')):
            subprocess.run(['git', 'init'], cwd=repo_copy, capture_output=True)
            subprocess.run(['git', 'add', '.'], cwd=repo_copy, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_copy, capture_output=True)
        
        # Apply all fixes
        for fix in fixes:
            try:
                file_path = fix['file']
                # Use the full path as provided in the fix
                full_path = os.path.join(repo_copy, *file_path.split('/'))
                
                # Read the current file content
                with open(full_path, 'r') as f:
                    lines = f.readlines()
                    current_content = ''.join(lines)
                
                search_content = fix['search'].strip()
                replace_content = fix['replace'].strip()
                
                # If line numbers are provided in the fix
                if 'line_number' in fix and fix['line_number']:
                    start_line = fix['line_number'] - 1  # Convert to 0-based index
                    window_start = max(0, start_line - 2)
                    window_end = min(len(lines), start_line + len(search_content.splitlines()) + 2)
                    
                    # Try to find exact content within window
                    found = False
                    for i in range(window_start, window_end):
                        window_content = ''.join(lines[i:i + len(search_content.splitlines())]).strip()
                        if window_content == search_content:
                            # Replace the content at the found position
                            lines[i:i + len(search_content.splitlines())] = replace_content.splitlines(True)
                            found = True
                            fix['score'] = 1
                            break
                    
                    if not found:
                        fix['score'] = 0
                        logger.error(f"Could not find matching content around line {start_line+1} in {file_path}")
                else:
                    # Fall back to simple string replacement
                    if search_content in current_content:
                        new_content = current_content.replace(search_content, replace_content)
                        lines = new_content.splitlines(True)
                        fix['score'] = 1
                    else:
                        fix['score'] = 0
                        logger.error(f"Could not find matching content in {file_path}")
                
                # Write back the modified content
                with open(full_path, 'w', newline='\n') as f:
                    f.writelines(lines)
                
            except Exception as e:
                logger.error(f"Error processing fix: {str(e)}", exc_info=True)
                fix['score'] = 0
                continue
            
        """
        Here We can run tests and implement a score system the one i built for agentless was:
        
        metrics["overall_score"] = (
            metrics["vote_frequency"] * 0.4 +                           # 40% weight - How often the patch appears
            metrics["regression_pass_rate"] * 0.3 +                     # 30% weight - How well it passes regression tests
            metrics["reproduction_pass_rate"] * 0.2 +                   # 20% weight - How well it passes reproduction tests
            (1 / (metrics["first_appearance_position"] + 1)) * 0.1      # 10% weight - Earlier appearances preferred
        )
        
        The weights are:
        - `vote_frequency` (0.4): Highest weight because frequent occurrence suggests higher confidence in the patch
        - `regression_pass_rate` (0.3): Second highest as regression tests check if the fix doesn't break existing functionality
        - `reproduction_pass_rate` (0.2): Important but slightly lower weight as these are new tests
        - `first_appearance_position` (0.1): Lowest weight, slightly favors patches that appeared earlier in the sequence
        """
        
        # Get consolidated diff of all changes
        diff_result = subprocess.run(
            ['git', 'diff'],
            cwd=repo_copy,
            capture_output=True,
            text=True
        )
        consolidated_diff = diff_result.stdout

    logger.step_end("Validating Fixes", f"Validated {len(fixes)} fixes")
    return fixes, consolidated_diff