from pathlib import Path
from typing import Dict, Optional
import json
import os
from datetime import datetime


from bug_localization import locate_buggy_files, identify_irrelevant_folders, locate_code_elements, locate_specific_lines
from bug_repair import generate_fixes
from fix_validation import generate_tests, validate_fixes
from llm import LLMInterface

from logger import logger

import dotenv
dotenv.load_dotenv()


def setup_directories(base_dir: str) -> Dict[str, str]:
    """Create necessary directories for outputs."""
    directories = [
        "file_level",
        "irrelevant_folders",
        "code_elements",
        "edit_locations",
        "repairs",
        "tests",
        "validation"
    ]
    
    for directory in directories:
        path = os.path.join(base_dir, directory)
        os.makedirs(path, exist_ok=True)
        logger.info(f"Created directory: {path}")
    
    return {dir_name: os.path.join(base_dir, dir_name) for dir_name in directories}

def save_results(results: Dict, output_file: str) -> None:
    """Save results to a JSON file."""
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved to {output_file}")



def find_patch(bug_description: str, project_dir: str, instance_id: str = None) -> Optional[str]:
    """
    Find a patch for the given bug description in the project directory.
    
    Args:
        bug_description (str): Description of the bug to fix
        project_dir (str): Path to the project directory
        instance_id (str): Unique identifier for this bug fix attempt
        
    Returns:
        Optional[str]: The best fix if found, None otherwise
    """
    
    if not instance_id:
        instance_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Fixed parameters
    output_dir = os.path.join("results", instance_id)
    top_n = 3
    context_window = 0
    max_samples = 1
    
    # Create single LLM instance
    # For Bedrock (commented out)
    # llm = LLMInterface(
    #     model_name="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
    #     temperature=0.1,
    #     max_tokens=4096,
    #     aws_region="us-west-2"
    # )

    # For Azure
    # llm = LLMInterface(
    #     model_name=f"azure/{os.getenv('AZURE_DEPLOYMENT_NAME')}",
    #     temperature=0.1,
    #     max_tokens=4096,
    #     api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    #     api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    #     api_version=os.getenv("AZURE_OPENAI_API_VERSION")
    # )

    # Active Vertex AI initialization
    llm = LLMInterface(
        model_name="vertex_ai/claude-3-7-sonnet@20250219",
        temperature=0.1,
        max_tokens=4096,
        security_key_path="security-key.json",
        vertex_location="us-east5"
    )


    
    # Create output directories
    dirs = setup_directories(output_dir)
    
    # Stage 1: Bug Location Discovery
    logger.info("Stage 1: Bug Location Discovery")
    
    buggy_files = locate_buggy_files(
        llm=llm,
        problem_statement=bug_description,
        repo_path=project_dir,
        output_dir=output_dir
    )
    save_results(buggy_files, os.path.join(dirs["file_level"], "buggy_files.json"))
    
    
    # irrelevant_folders = identify_irrelevant_folders(
    #     llm=llm,
    #     problem_statement=bug_description,
    #     repo_path=project_dir,
    #     output_dir=output_dir
    # )
    # save_results(irrelevant_folders, os.path.join(dirs["irrelevant_folders"], "irrelevant_folders.json"))
    
    
    # Stage 2: Deep Bug Analysis
    logger.info("Stage 2: Deep Bug Analysis")
    
    if not buggy_files:
        logger.warning("No buggy files found to analyze")
        return None
        
    code_elements = locate_code_elements(
        llm=llm,
        problem_statement=bug_description,
        repo_path=project_dir,
        buggy_files=buggy_files[:top_n],
        output_dir=output_dir
    )
    
    if not code_elements:
        logger.warning("No code elements identified for analysis")
        return None
        
    save_results(code_elements, os.path.join(dirs["code_elements"], "code_elements.json"))
    
    
    edit_locations = locate_specific_lines(
        llm=llm,
        problem_statement=bug_description,
        repo_path=project_dir,
        code_elements=code_elements,
        context_window=context_window,
        output_dir=output_dir
    )
    save_results(edit_locations, os.path.join(dirs["edit_locations"], "edit_locations.json"))
    
    # Stage 3: Fix Generation
    logger.info("Stage 3: Fix Generation")
    fixes = generate_fixes(
        llm=llm,
        problem_statement=bug_description,
        repo_path=project_dir,
        edit_locations=edit_locations,
        context_window=context_window,
        output_dir=output_dir
    )
    save_results(fixes, os.path.join(dirs["repairs"], "fixes.json"))
    
    # Stage 4: Fix Validation
    logger.info("Stage 4: Fix Validation")
    
    tests = generate_tests(
        llm=llm,
        problem_statement=bug_description,
        repo_path=project_dir,
        output_dir=output_dir
    )
    save_results(tests, os.path.join(dirs["tests"], "tests.json"))
    
    validation_results, consolidated_diff = validate_fixes(
        repo_path=project_dir,
        fixes=fixes,
        tests=tests,
        output_dir=output_dir,
        # instance_id=instance_id
    )
    save_results(validation_results, os.path.join(dirs["validation"], "validation_results.json"))
    
    return consolidated_diff


if __name__ == "__main__":
    instance_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    patch = find_patch(
        'There is a bug in the get_cart_total endpoint where it randomly skips items during total calculation.',
        'test-app'
    )

    # Print the results
    print('\n' + '=' * 50)
    if patch:
        print('🎉 Bug Fix Generated Successfully!')
        print('=' * 50)
        print(patch)
        print('=' * 50)
        print(f'Results saved in: results/{instance_id}/')
    else:
        print('❌ Bug Fix Generation Failed')
        print('=' * 50)
        print("No patch was generated or an error occurred")
    print('=' * 50)
