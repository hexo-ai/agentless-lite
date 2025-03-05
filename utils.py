import ast
from datetime import datetime
import os
from typing import Dict, List
from logger import logger


def save_llm_response(output_dir: str, stage: str, response: str, details: str = "") -> None:
    """Save LLM response to a file."""
    response_dir = os.path.join(output_dir, stage)
    os.makedirs(response_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.txt"
    
    with open(os.path.join(response_dir, filename), 'w') as f:
        f.write(f"=== Details ===\n{details}\n\n=== Response ===\n{response}")
        
def create_file_skeleton(content: str, line_numbers: bool = True) -> str:
    """
    Create a skeleton version of the file content.
    
    Args:
        content: The file content to create skeleton from
        line_numbers: Whether to include line numbers in output (default: True)
    """
    skeleton_lines = []
    lines = content.split('\n')
    current_line_num = 1
    last_line_num = 0
    current_indent = 0
    
    # Calculate the maximum width needed for line numbers
    max_line_num = len(lines)
    line_num_width = len(str(max_line_num))
    
    for line in lines:
        stripped = line.strip()
        if not stripped:  # Skip empty lines
            current_line_num += 1
            continue
            
        # Calculate indentation level
        indent = len(line) - len(line.lstrip())
        
        # Keep important structural elements
        if any(keyword in stripped for keyword in ['class ', 'def ', 'async def ']):
            if last_line_num and current_line_num - last_line_num > 1:
                skeleton_lines.append("..." if not line_numbers else "..." + " " * line_num_width)
            skeleton_lines.append(
                line if not line_numbers else f"{str(current_line_num).rjust(line_num_width)} |{line}"
            )
            last_line_num = current_line_num
            current_indent = indent
            
        # Keep top-level variable declarations only
        elif '=' in stripped and not stripped.startswith('#'):
            if indent == 0 and any(keyword in stripped.split('=')[0] for keyword in ['var', 'let', 'const', ': Dict', ': List', ': Set']):
                if last_line_num and current_line_num - last_line_num > 1:
                    skeleton_lines.append("..." if not line_numbers else "..." + " " * line_num_width)
                skeleton_lines.append(
                    line if not line_numbers else f"{str(current_line_num).rjust(line_num_width)} |{line}"
                )
                last_line_num = current_line_num
                
        # Keep imports
        elif any(keyword in stripped for keyword in ['import ', 'from ']):
            if last_line_num and current_line_num - last_line_num > 1:
                skeleton_lines.append("..." if not line_numbers else "..." + " " * line_num_width)
            skeleton_lines.append(
                line if not line_numbers else f"{str(current_line_num).rjust(line_num_width)} |{line}"
            )
            last_line_num = current_line_num
            
        current_line_num += 1
    
    return '\n'.join(skeleton_lines)

def read_file_content(file_path: str, line_no: bool = True) -> str:
    """Read and return the content of a file with optional line numbers."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            if line_no:
                # Calculate padding needed based on total number of lines
                max_line_num = len(lines)
                padding = len(str(max_line_num))
                
                # Add line numbers with proper padding
                numbered_lines = []
                for i, line in enumerate(lines):
                    line_num = str(i + 1)
                    # Right-align the line number and add spaces to maintain alignment
                    padded_num = line_num.rjust(padding)
                    numbered_lines.append(f"{padded_num}|{line}")
                content = ''.join(numbered_lines)
            else:
                content = ''.join(lines)
                
            logger.debug(f"Successfully read file: {file_path}")
            return content
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        return ""

def extract_context(content: str, location: Dict, context_window: int) -> str:
    """Extract context around a specific location in the code."""
    lines = content.split('\n')
    
    # Handle location format from locate_specific_lines
    if 'start' in location and 'end' in location:
        return location['context']
    
    # Handle location format from locate_code_elements
    elif 'type' in location and location['type'] == 'line':
        try:
            line_num = int(location['name'])
            start = max(0, line_num - context_window)
            end = min(len(lines), line_num + context_window)
            return '\n'.join(lines[start:end])
        except ValueError:
            logger.error(f"Invalid line number: {location['name']}")
            return content
    
    else:
        logger.error(f"Invalid location format: {location}")
        return content

def extract_relevant_sections(file_path: str, repo_path: str, elements: List[Dict], context_window: int) -> List[str]:
    """Extract relevant code sections using AST parsing."""
    full_path = os.path.join(repo_path, file_path)
    if not os.path.exists(full_path):
        logger.error(f"File not found: {file_path}")
        return []
    
    logger.info(f"Starting to process elements in extract_relevant_sections from {file_path}")
    for element in elements:
        logger.info(f"Processing element - Type: {element['type']}, Name: {element['name']}")
        
    with open(full_path, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    sections = []
    
    # Parse the Python code into an AST
    tree = ast.parse(content)
    
    for element in elements:
        section_content = []
        if element['type'] == 'function':
            logger.info(f"Searching for function: {element['name']}")
            for node in ast.walk(tree):
                # Check for both regular and async functions
                if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) 
                    and node.name == element['name']):
                    start = node.lineno - 1
                    end = node.end_lineno
                    logger.info(f"Found function '{element['name']}' from line {start+1} to {end}")
                    
                    # Add context window
                    start = max(0, start - context_window)
                    end = min(len(lines), end + context_window)
                    
                    # Add header and content
                    section_content.append(f"=== Function: {element['name']} ===")
                    section_content.append("-" * 40)
                    section_content.extend(lines[start:end])
                    section_content.append("-" * 40)
                    
                    section = '\n'.join(section_content)
                    sections.append(section)
                    logger.info(f"Extracted section:\n{section}")
                    break
                    
        elif element['type'] == 'class':
            logger.info(f"Searching for class: {element['name']}")
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == element['name']:
                    start = node.lineno - 1
                    end = node.end_lineno
                    logger.info(f"Found class '{element['name']}' from line {start+1} to {end}")
                    
                    # Add context window
                    start = max(0, start - context_window)
                    end = min(len(lines), end + context_window)
                    
                    # Add header and content
                    section_content.append(f"=== Class: {element['name']} ===")
                    section_content.append("-" * 40)
                    section_content.extend(lines[start:end])
                    section_content.append("-" * 40)
                    
                    section = '\n'.join(section_content)
                    sections.append(section)
                    logger.info(f"Extracted section:\n{section}")
                    break
                    
        elif element['type'] == 'variable':
            logger.info(f"Searching for variable: {element['name']}")
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == element['name']:
                            start = node.lineno - 1
                            end = node.end_lineno
                            logger.info(f"Found variable '{element['name']}' from line {start+1} to {end}")
                            
                            # Add context window
                            start = max(0, start - context_window)
                            end = min(len(lines), end + context_window)
                            
                            # Add header and content
                            section_content.append(f"=== Variable: {element['name']} ===")
                            section_content.append("-" * 40)
                            section_content.extend(lines[start:end])
                            section_content.append("-" * 40)
                            
                            section = '\n'.join(section_content)
                            sections.append(section)
                            logger.info(f"Extracted section:\n{section}")
                            break
                            
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    if node.target.id == element['name']:
                        start = node.lineno - 1
                        end = node.end_lineno
                        logger.info(f"Found variable '{element['name']}' from line {start+1} to {end}")
                        
                        # Add context window
                        start = max(0, start - context_window)
                        end = min(len(lines), end + context_window)
                        
                        # Add header and content
                        section_content.append(f"=== Variable: {element['name']} ===")
                        section_content.append("-" * 40)
                        section_content.extend(lines[start:end])
                        section_content.append("-" * 40)
                        
                        section = '\n'.join(section_content)
                        sections.append(section)
                        logger.info(f"Extracted section:\n{section}")
                        break
    
    logger.info("Completed processing elements in extract_relevant_sections.")
    return sections

