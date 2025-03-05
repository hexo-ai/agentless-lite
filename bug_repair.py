from typing import Dict, List
from llm import LLMInterface
import os

from logger import logger
from utils import extract_relevant_sections, save_llm_response


def generate_fixes(
    llm: LLMInterface,
    problem_statement: str,
    repo_path: str,
    edit_locations: Dict,
    context_window: int,
    max_samples: int,
    output_dir: str
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
    
    # Combine all contents
    combined_content = "\n\n".join(all_file_contents)
    
    # Generate fixes for all locations at once
    for sample_idx in range(max_samples):
        logger.info(f"Generating sample {sample_idx + 1}/{max_samples}")
        
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
                    if '<<<<<<< SEARCH' in edit_command:
                        # Extract file path from the edit command
                        file_path = edit_command.split('###')[1].strip().split('\n')[0].strip()
                        
                        # Find matching location for this file
                        matching_location = None
                        if file_path in edit_locations:
                            matching_location = next(
                                (loc for loc in edit_locations[file_path] 
                                 if loc['content'] in edit_command),
                                edit_locations[file_path][0]  # fallback to first location
                            )
                        
                        fixes.append({
                            "file": file_path,
                            "location": matching_location,
                            "fix": edit_command,
                            "score": 0
                        })
                        logger.info(f"Successfully generated fix for {file_path}")
            
        except Exception as e:
            logger.error(f"Error processing fix sample {sample_idx + 1}: {str(e)}")
    
    logger.step_end("Generating Fixes", f"Generated {len(fixes)} valid fixes")
    return fixes