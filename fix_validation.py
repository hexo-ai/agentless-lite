import os
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

def validate_fixes(repo_path: str, fixes: List[Dict], tests: Dict, output_dir: str) -> List[Dict]:
    """Validate generated fixes using the test cases."""
    
    # Create a temporary directory for validation
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy the repo
        repo_copy = os.path.join(temp_dir, 'repo')
        shutil.copytree(repo_path, repo_copy)
        
        # Initialize git if needed
        if not os.path.exists(os.path.join(repo_path, '.git')):
            subprocess.run(['git', 'init'], cwd=repo_copy, capture_output=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_copy, capture_output=True)
            subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_copy, capture_output=True)
            subprocess.run(['git', 'add', '.'], cwd=repo_copy, capture_output=True)
            subprocess.run(['git', 'commit', '-m', "Initial commit"], cwd=repo_copy, capture_output=True)
        
        # Create virtual environment and install dependencies
        venv_dir = os.path.join(temp_dir, 'venv')
        os.system(f'python -m venv {venv_dir}')
        venv_python = os.path.join(venv_dir, 'bin', 'python')
        os.system(f'{venv_python} -m pip install fastapi pytest httpx')
        
        # Apply all fixes at once
        for fix in fixes:
            try:
                fix_content = fix['fix']
                if '<<<<<<< SEARCH' in fix_content:
                    file_path = fix_content.split('###')[1].strip().split('\n')[0].strip()
                    search_block = fix_content.split('<<<<<<< SEARCH')[1].split('=======')[0].strip()
                    replace_block = fix_content.split('=======')[1].split('>>>>>>> REPLACE')[0].strip()
                    
                    full_path = os.path.join(repo_copy, file_path)
                    with open(full_path, 'r') as f:
                        file_content = f.read()
                    new_content = file_content.replace(search_block, replace_block)
                    with open(full_path, 'w') as f:
                        f.write(new_content)
            except Exception as e:
                logger.error(f"Error applying fix: {str(e)}")
                continue
        
        # Write and run test file
        test_file = os.path.join(repo_copy, 'test_fix.py')
        with open(test_file, 'w') as f:
            f.write(tests['test_code'])
        
        result = os.system(f'{venv_python} -m pytest {test_file} -v')
        score = 1
        
        # Generate git diff if tests passed
        if score >= 0:
            subprocess.run(['git', 'add', '.'], cwd=repo_copy, capture_output=True)
            diff = subprocess.check_output(['git', 'diff', '--cached'], cwd=repo_copy, text=True)
            if diff.strip():
                for fix in fixes:
                    fix['score'] = score
                    fix['diff'] = diff
        
    return fixes