from typing import Optional, Dict, Any
from litellm import completion

from logger import logger


class LLMInterface:
    # Prompt templates (add these at the class level)
    FILE_SEARCH_PROMPT = """
Please look through the following GitHub problem description and Repository structure and provide a list of files that one would need to edit to fix the problem.

### GitHub Problem Description ###
{problem_statement}

###

### Repository Structure ###
{structure}

###

Please only provide the full path and return at most 5 files.
The returned files should be separated by new lines ordered by most to least important and wrapped with ```
For example:
```
file1.py
file2.py
```
"""

    IRRELEVANT_FOLDERS_PROMPT = """
Please look through the following GitHub problem description and Repository structure and provide a list of folders that are irrelevant to fixing the problem.
Note that irrelevant folders are those that do not need to be modified and are safe to ignored when trying to solve this problem.

### GitHub Problem Description ###
{problem_statement}

###

### Repository Structure ###
{structure}

###

Please only provide the full path.
Remember that any subfolders will be considered as irrelevant if you provide the parent folder.
Please ensure that the provided irrelevant folders do not include any important files needed to fix the problem
The returned folders should be separated by new lines and wrapped with ```
For example:
```
folder1/
folder2/folder3/
folder4/folder5/
```
"""
    CODE_ELEMENTS_PROMPT = """
Please look through the following GitHub Problem Description and the Skeleton of Relevant Files.
Identify all locations that need inspection or editing to fix the problem, including directly related areas as well as any potentially related global variables, functions, and classes.
For each location you provide, either give the name of the class, the name of a method in a class, the name of a function, or the name of a global variable.

### GitHub Problem Description ###
{problem_statement}

### Skeleton of Relevant Files ###
{file_contents}

###

Please provide the complete set of locations as either a class name, a function name, or a variable name.
Note that if you include a class, you do not need to list its specific methods.
You can include either the entire class or don't include the class name and instead include specific methods in the class.
### Examples:
```
full_path1/file1.py
function: my_function_1
class: MyClass1
function: MyClass2.my_method

full_path2/file2.py
variable: my_var
function: MyClass3.my_method

full_path3/file3.py
function: my_function_2
function: my_function_3
function: MyClass4.my_method_1
class: MyClass5
```

Return just the locations wrapped with ```.    
"""

    LINE_LEVEL_PROMPT = """
Please review the following GitHub problem description and relevant files, and provide a set of locations that need to be edited to fix the issue.
The locations can be specified as class names, function or method names, that require modification.

### GitHub Problem Description ###
{problem_statement}

###
{file_contents}

###

Please provide the class name, function or method name, that need to be edited.
The possible location outputs should be either "class", "function"

### Examples:
```
full_path1/file1.py
function: my_function_1
class: MyClass1
function: MyClass2.my_method

full_path2/file2.py
variable: my_var
function: MyClass3.my_method

full_path3/file3.py
function: my_function_2
function: my_function_3
function: MyClass4.my_method_1
class: MyClass5
```

Return just the location(s) wrapped with ```.
    
"""


    GENERATE_FIX_PROMPT = """
We are currently solving the following issue within our repository. Here is the issue text:
--- BEGIN ISSUE ---
{problem_statement}
--- END ISSUE ---

{repair_relevant_file_instruction}
--- BEGIN FILE ---
```
{content}
```
--- END FILE ---

Please first localize the bug based on the issue statement, and then generate *SEARCH/REPLACE* edits to fix the issue.

Every *SEARCH/REPLACE* edit must use this format:
1. The file path with line numbers
2. The start of search block: <<<<<<< SEARCH (line X-Y)
3. A contiguous chunk of lines to search for in the existing source code
4. The dividing line: =======
5. The lines to replace into the source code
6. The end of the replace block: >>>>>>> REPLACE

Here is an example:

```python
### mathweb/flask/app.py
<<<<<<< SEARCH (line X-Y)
from flask import Flask
=======
import math
from flask import Flask
>>>>>>> REPLACE
```

Please note that the *SEARCH/REPLACE* edit REQUIRES PROPER INDENTATION. If you would like to add the line '        print(x)', you must fully write that out, with all those spaces before the code!
Wrap the *SEARCH/REPLACE* edit in blocks ```python...```. 

"""

    file_content_template = """
### File: {file_name} ###
{file_content}
"""
    file_content_in_block_template = """
### File: {file_name} ###
```python
{file_content}
```
"""

    def __init__(self):
        self.model_name = "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
        self.aws_region = "us-west-2"
        self.default_temperature = 0.1
        self.max_tokens = 4096

    def call_llm(self, 
                prompt: str, 
                temperature: Optional[float] = None,
                max_tokens: Optional[int] = None,
                **kwargs) -> str:
        """
        Call the LLM with a given prompt and return the response.
        
        Args:
            prompt (str): The prompt to send to the LLM
            temperature (float, optional): Sampling temperature
            max_tokens (int, optional): Maximum tokens in response
            **kwargs: Additional arguments to pass to the LLM
        """
        try:
            logger.llm_request(
                prompt=prompt,
                temperature=temperature or self.default_temperature,
                max_tokens=max_tokens or self.max_tokens,
                **kwargs
            )
            
            response = completion(
                model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature or self.default_temperature,
                max_tokens=max_tokens or self.max_tokens,
                aws_region_name="us-west-2",
                **kwargs
            )
            
            result = response.choices[0].message.content
            logger.llm_response(result)
            
            return result

        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}")
            raise

