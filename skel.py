import os
from typing import List, Dict

def read_file_content(file_path: str) -> str:
    """Read and return the content of a file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {str(e)}")
        return ""

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

def test_skeleton_creation():
    """Test the skeleton creation with a sample file."""
    test_content = """import os
from typing import List

class TestClass:
    def __init__(self):
        self.x = 1
        some_var = 42
        
    def test_method(self):
        local_var = 123
        pass
        
def main_function():
    # Some comment
    x = 5
    my_list: List[int] = []
    return x

# Some space here


var = 10
items_db: Dict[int, Dict] = {}
"""
    
    # Write test content to a file
    with open('test_file.py', 'w') as f:
        f.write(test_content)
    
    # Read and create skeleton with and without line numbers
    content = read_file_content('test_file.py')
    skeleton_with_lines = create_file_skeleton(content, line_numbers=True)
    skeleton_without_lines = create_file_skeleton(content, line_numbers=False)
    
    print("Original content:")
    print("----------------")
    print(test_content)
    print("\nSkeleton content (with line numbers):")
    print("----------------")
    print(skeleton_with_lines)
    print("\nSkeleton content (without line numbers):")
    print("----------------")
    print(skeleton_without_lines)
    
    # Cleanup
    os.remove('test_file.py')

if __name__ == "__main__":
    test_skeleton_creation()