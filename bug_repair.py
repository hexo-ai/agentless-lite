from typing import Dict, List
from llm import LLMInterface
import os
import re
import logging

from logger import logger
from utils import extract_relevant_sections, save_llm_response


def generate_fixes(
    llm: LLMInterface,
    problem_statement: str,
    repo_path: str,
    edit_locations: Dict,
    context_window: int,
    output_dir: str,
    max_samples: int = 1
) -> List[Dict]:
    """Generate potential fixes for identified bugs."""
    logger.step_start("Generating Fixes")
    fixes = []
    
    # Collect relevant code sections
    all_file_contents = []
    for file_path, locations in edit_locations.items():
        sections = []
        for location in locations:
            if location['type'] == 'line':
                # For line-type locations, use the content directly
                sections.append(location['content'])
            elif 'name' in location:
                # For named elements (functions, classes), use extract_relevant_sections
                extracted = extract_relevant_sections(file_path, repo_path, [location], context_window)
                if extracted:
                    sections.extend(extracted)
        
        if sections:
            formatted_content = llm.file_content_in_block_template.format(
                file_name=file_path,
                file_content='\n\n'.join(sections)
            )
            all_file_contents.append(formatted_content)
            logger.info(f"Processed sections for {file_path}")
    
    if not all_file_contents:
        logger.warning("No file contents collected for fix generation")
        return fixes
        
    # Combine all contents
    combined_content = "\n\n".join(all_file_contents)
    
    # Generate fixes for all locations at once
    successful_fixes = 0
    for sample_idx in range(max_samples):
        logger.info(f"Generating sample {sample_idx + 1}/{max_samples}", color='cyan')
        
        prompt = llm.GENERATE_FIX_PROMPT.format(
            problem_statement=problem_statement,
            repair_relevant_file_instruction="Please fix the following code sections:",
            content=combined_content
        )
        
        response = llm.call_llm(prompt, temperature=0.8)
        save_llm_response(
            output_dir=output_dir,
            stage="repairs",
            response=response,
            details=f"Problem: {problem_statement}\nSample: {sample_idx + 1}"
        )

        try:             
            # Extract all fix commands from the response
            if '```python' in response:
                fix_blocks = response.split('```python')[1:]
                for block in fix_blocks:
                    edit_command = block.split('```')[0].strip()
                    
                    # Extract file path from the block
                    file_match = re.search(r'###\s*(.*?)\n', edit_command)
                    if not file_match:
                        continue
                    file_path = file_match.group(1).strip().strip('/')
                    
                    # Extract search and replace content with improved regex
                    search_replace_match = re.search(
                        r'<<<<<<< SEARCH(?:\s*\(line (\d+)(?:-(\d+))?\))?\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE',
                        edit_command,
                        re.DOTALL
                    )

                    if search_replace_match:
                        start_line = int(search_replace_match.group(1)) if search_replace_match.group(1) else None
                        end_line = int(search_replace_match.group(2)) if search_replace_match.group(2) else start_line
                        search_content = search_replace_match.group(3).strip()
                        replace_content = search_replace_match.group(4).strip()
                        
                        # Simplified matching logic - just check if file exists in edit_locations
                        matching_location = None
                        if file_path in edit_locations:
                            for location in edit_locations[file_path]:
                                if search_content.strip() in location['content'].strip():
                                    matching_location = location
                                    break
                        
                        fix = {
                            "file": file_path,
                            "location": matching_location,
                            "search": search_content,
                            "replace": replace_content,
                            "start_line": start_line,
                            "end_line": end_line,
                            "fix": edit_command,
                            "score": 0
                        }
                        fixes.append(fix)
                        logger.info(f"Successfully generated fix for {file_path}")
        
        except Exception as e:
            logger.error(f"Error processing fix sample {sample_idx + 1}: {str(e)}")
            continue
    
    logger.step_end("Generating Fixes", f"Generated {len(fixes)} valid fixes")
    return fixes