import os
from typing import List, Dict
from llm import LLMInterface
from logger import logger
from utils import create_file_skeleton, extract_relevant_sections, read_file_content, save_llm_response

def get_repo_structure(repo_path: str, extensions: List[str] = ['.py']) -> str:
    """Get repository structure as a string, filtering by file extensions."""
    structure = []
    for root, dirs, files in os.walk(repo_path):
        # Skip the root directory itself
        if root == repo_path:
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    structure.append(file)
            continue
            
        level = root.replace(repo_path, '').count(os.sep) - 1
        indent = '  ' * level
        structure.append(f'{indent}{os.path.basename(root)}/')
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                structure.append(f'{indent}  {file}')
    return '\n'.join(structure)



def locate_buggy_files(llm: LLMInterface, problem_statement: str, repo_path: str, output_dir: str) -> List[str]:
    """Identify potentially buggy files."""
    logger.step_start("Locating Buggy Files")
    
    repo_structure = get_repo_structure(repo_path)
    prompt = llm.FILE_SEARCH_PROMPT.format(
        problem_statement=problem_statement,
        structure=repo_structure
    )
    
    response = llm.call_llm(prompt)
    save_llm_response(
        output_dir=output_dir,
        stage="file_level",
        response=response,
        details=f"Problem: {problem_statement}\nRepo Structure: {repo_structure}"
    )
    
    try:
        if '```' in response:
            files = response.split('```')[1].strip().split('\n')
        else:
            files = [line.strip() for line in response.split('\n') if line.strip()]
        
        result = [f.strip() for f in files if f.strip() and not f.startswith('```')]
        logger.step_end("Locating Buggy Files", result)
        return result
        
    except Exception as e:
        logger.error(f"Error parsing buggy files response: {str(e)}")
        return []

def identify_irrelevant_folders(llm: LLMInterface, problem_statement: str, repo_path: str, output_dir:str) -> List[str]:
    """Identify folders that can be safely ignored."""
    repo_structure = get_repo_structure(repo_path)
    prompt = llm.IRRELEVANT_FOLDERS_PROMPT.format(
        problem_statement=problem_statement,
        structure=repo_structure
    )
    
    response = llm.call_llm(prompt)
    save_llm_response(
        output_dir=output_dir,
        stage="irrelevant_folders",
        response=response,
        details=f"Problem: {problem_statement}\nRepo Structure: {repo_structure}"
    )
    
    try:
        # Extract content between ``` markers, handling potential variations
        if '```' in response:
            folders = response.split('```')[1].strip().split('\n')
        else:
            folders = [line.strip() for line in response.split('\n') if line.strip()]
        return [f.strip() for f in folders if f.strip() and not f.startswith('```')]
    except Exception as e:
        logger.warning(f"Error parsing irrelevant folders response: {str(e)}")
        return []

def locate_code_elements(llm: LLMInterface, problem_statement: str, repo_path: str, buggy_files: List[str], output_dir:str) -> Dict:
    """Identify relevant code elements in buggy files."""
    logger.step_start("Locating Code Elements")
    
    file_contents = {}
    for file_path in buggy_files:
        full_path = os.path.join(repo_path, file_path)
        if os.path.exists(full_path):
            content = read_file_content(full_path, False)
            if content:
                # Create skeleton version for analysis
                skeleton = create_file_skeleton(content)
                file_contents[file_path] = skeleton
                logger.debug(f"Skeleton for {file_path}:\n{skeleton}")
            else:
                logger.warning(f"Empty or unreadable file: {file_path}")
    
    if not file_contents:
        logger.warning("No file contents found to analyze")
        return {}
    
    # Format using template from llm.py
    combined_contents = "\n\n".join([
        llm.file_content_in_block_template.format(
            file_name=file_path,
            file_content=content
        )
        for file_path, content in file_contents.items()
    ])
    
    # Use the CODE_ELEMENTS_PROMPT from llm.py
    prompt = llm.CODE_ELEMENTS_PROMPT.format(
        problem_statement=problem_statement,
        file_contents=combined_contents
    )
    
    response = llm.call_llm(prompt)
    save_llm_response(
        output_dir=output_dir,
        stage="code_elements",
        response=response
    )
    
    elements = {}
    try:
        if '```' in response:
            content = response.split('```')[1].strip()
            current_file = None
            
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                if ':' not in line:
                    current_file = line
                    elements[current_file] = []
                else:
                    try:
                        element_type, name = line.split(': ', 1)
                        if element_type in ['class', 'function', 'variable']:
                            elements[current_file].append({
                                "type": element_type,
                                "name": name.strip()
                            })
                    except ValueError:
                        continue
                        
    except Exception as e:
        logger.error(f"Error parsing code elements: {str(e)}")
    
    logger.step_end("Locating Code Elements", elements)
    return elements



def locate_specific_lines(llm: LLMInterface, problem_statement: str, repo_path: str, code_elements: Dict, context_window: int, output_dir: str) -> Dict:
    """Identify specific lines that need modification."""
    edit_locations = {}
    
    # Collect relevant code sections
    all_file_contents = []
    for file_path, elements in code_elements.items():
        sections = extract_relevant_sections(file_path, repo_path, elements, context_window)
        if sections:
            formatted_content = llm.file_content_in_block_template.format(
                file_name=file_path,
                file_content='\n'.join(sections)
            )
            all_file_contents.append(formatted_content)
    
    combined_content = "\n\n".join(all_file_contents)
    
    prompt = llm.LINE_LEVEL_PROMPT.format(
        problem_statement=problem_statement,
        file_contents=combined_content
    )
    
    response = llm.call_llm(prompt)
    save_llm_response(
        output_dir=output_dir,
        stage="line_level",
        response=response,
        details=f"All files analysis"
    )
    
    try:
        if '```' in response:
            content = response.split('```')[1].strip()
            current_file = None
            
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if ':' not in line:
                    current_file = line
                    if current_file not in edit_locations:
                        edit_locations[current_file] = []
                else:
                    element_type, name = line.split(': ', 1)
                    if element_type == 'function':
                        # Find the function in code_elements
                        if current_file in code_elements:
                            matching_elements = [
                                elem for elem in code_elements[current_file] 
                                if elem['type'] == 'function' and elem['name'] == name.strip()
                            ]
                            if matching_elements:
                                # Get the function content using extract_relevant_sections
                                sections = extract_relevant_sections(
                                    current_file, 
                                    repo_path, 
                                    [matching_elements[0]], 
                                    context_window
                                )
                                if sections:
                                    edit_locations[current_file].append({
                                        "type": "function",
                                        "name": name.strip(),
                                        "content": sections[0]
                                    })
                    
                    elif line.startswith('line: '):
                        try:
                            line_num = int(line.split('line: ')[1])
                            content = read_file_content(os.path.join(repo_path, current_file))
                            if content:
                                start_line = max(1, line_num - context_window)
                                end_line = min(len(content.split('\n')), line_num + context_window)
                                edit_locations[current_file].append({
                                    "type": "line",
                                    "start": start_line,
                                    "end": end_line,
                                    "content": '\n'.join(content.split('\n')[start_line-1:end_line])
                                })
                        except ValueError:
                            continue
                            
    except Exception as e:
        logger.error(f"Error parsing line-level response: {str(e)}")
    
    return edit_locations

