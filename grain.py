import os
from typing import List, Dict
import ast

from utils import read_file_content

def extract_relevant_sections(file_path: str, repo_path: str, elements: List[Dict], context_window: int) -> List[str]:
    """Extract relevant code sections using AST parsing."""
    full_path = os.path.join(repo_path, file_path)
    if not os.path.exists(full_path):
        print(f"File not found: {file_path}")
        return []
        
    # Read the file content
    with open(full_path, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    sections = []
    
    # Parse the Python code into an AST
    tree = ast.parse(content)
    
    for element in elements:
        if element['type'] == 'function':
            # Find function definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == element['name']:
                    start = node.lineno - 1
                    end = node.end_lineno
                    
                    # Add context window
                    start = max(0, start - context_window)
                    end = min(len(lines), end + context_window)
                    
                    sections.append('\n'.join(lines[start:end]))
                    break
                    
        elif element['type'] == 'class':
            # Find class definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == element['name']:
                    start = node.lineno - 1
                    end = node.end_lineno
                    
                    # Add context window
                    start = max(0, start - context_window)
                    end = min(len(lines), end + context_window)
                    
                    sections.append('\n'.join(lines[start:end]))
                    break
                    
        elif element['type'] == 'variable':
            # Find variable assignments (both regular and annotated)
            for node in ast.walk(tree):
                # Regular assignments
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == element['name']:
                            start = node.lineno - 1
                            end = node.end_lineno
                            
                            # Add context window
                            start = max(0, start - context_window)
                            end = min(len(lines), end + context_window)
                            
                            sections.append('\n'.join(lines[start:end]))
                            break
                # Type-annotated assignments
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == element['name']:
                    start = node.lineno - 1
                    end = node.end_lineno
                    
                    # Add context window
                    start = max(0, start - context_window)
                    end = min(len(lines), end + context_window)
                    
                    sections.append('\n'.join(lines[start:end]))
                    break
    
    return sections

def create_test_file():
    """Create a test file with sample content."""
    test_content = """import os
from typing import Dict, List

items_db: Dict[int, Dict] = {
    1: {"name": "item1", "price": 10},
    2: {"name": "item2", "price": 20}
}

shopping_carts: Dict[int, List[int]] = {}

def add_to_cart(user_id: int, item_id: int):
    if user_id not in shopping_carts:
        shopping_carts[user_id] = []
    shopping_carts[user_id].append(item_id)
    return True

def get_cart_total(user_id: int) -> float:
    if user_id not in shopping_carts:
        return 0.0
    
    total = 0.0
    for item_id in shopping_carts[user_id]:
        if item_id in items_db:
            total += items_db[item_id]["price"]
    return total

class ShoppingCart:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.items = []
"""
    
    with open('test_cart.py', 'w') as f:
        f.write(test_content)
    return test_content

def test_extract_sections():
    """Test the extract_relevant_sections function."""
    # Create test file
    test_content = create_test_file()
    
    # Test elements
    elements = [
        {"type": "variable", "name": "items_db"},
        {"type": "variable", "name": "shopping_carts"},
        {"type": "function", "name": "get_cart_total"},
        {"type": "function", "name": "add_to_cart"},
        {"type": "class", "name": "ShoppingCart"}
    ]
    
    # Extract sections
    sections = extract_relevant_sections("test_cart.py", ".", elements, context_window=2)
    
    # Cleanup
    os.remove('test_cart.py')

if __name__ == "__main__":
    test_extract_sections()