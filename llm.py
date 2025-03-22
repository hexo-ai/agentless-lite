from typing import Optional, Dict, Any
from litellm import completion
import json
import os

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

    def __init__(self, 
                model_name: str = "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0", 
                temperature: float = 0.1,
                max_tokens: int = 4096,
                **kwargs):
        """
        Initialize the LLMInterface with configurable model settings.
        
        Args:
            model_name: The model identifier (bedrock/*, vertex_ai/*, or azure/*)
            temperature: The sampling temperature for the model
            max_tokens: Maximum number of tokens to generate
            **kwargs: Additional configuration options based on model provider
        """
        # Base configuration
        self.model_name = model_name
        self.default_temperature = temperature
        self.max_tokens = max_tokens
        
        # Provider-specific configurations
        if model_name.startswith("bedrock/"):
            self.aws_region = kwargs.get("aws_region", "us-west-2")
        elif model_name.startswith("vertex_ai/"):
            security_key_path = kwargs.get("security_key_path")
            if security_key_path:
                self.configure_vertex(security_key_path, kwargs.get("vertex_location", "us-east5"))
            else:
                self.vertex_project = None
                self.vertex_location = None
                self.vertex_credentials = None
        elif model_name.startswith("azure/"):
            # Azure configuration
            self.azure_api_base = kwargs.get("api_base")
            self.azure_api_key = kwargs.get("api_key")
            self.azure_api_version = kwargs.get("api_version")
        
        # Set litellm verbose mode if specified
        import litellm
        litellm.set_verbose = kwargs.get("verbose", False)
        
    def configure_vertex(self, security_key_path: str, location: str = "us-east5"):
        """Configure Vertex AI settings"""
        with open(security_key_path, 'r') as file:
            self.vertex_credentials = json.load(file)
        
        self.vertex_project = self.vertex_credentials.get("project_id")
        self.vertex_location = location
        
        # Set environment variables for Vertex AI
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = security_key_path
        os.environ["GOOGLE_CLOUD_PROJECT"] = self.vertex_project
        os.environ["VERTEXAI_PROJECT"] = self.vertex_project
        os.environ["VERTEXAI_LOCATION"] = location

    def configure_azure(self, api_base: str, api_key: str, api_version: str):
        """Configure Azure OpenAI settings"""
        self.azure_api_base = api_base
        self.azure_api_key = api_key
        self.azure_api_version = api_version

    def call_llm(self, 
                prompt: str, 
                temperature: Optional[float] = None,
                max_tokens: Optional[int] = None,
                **kwargs) -> str:
        """
        Call the LLM with a given prompt and return the response.
        Supports Bedrock, Vertex AI and Azure models.
        """
        try:
            logger.llm_request(
                prompt=prompt,
                temperature=temperature or self.default_temperature,
                max_tokens=max_tokens or self.max_tokens,
                **kwargs
            )
            
            messages = [{"role": "user", "content": prompt}]
            
            completion_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature or self.default_temperature,
                "max_tokens": max_tokens or self.max_tokens,
                **kwargs
            }
            
            # Add provider-specific parameters
            if self.model_name.startswith("vertex_ai/") and hasattr(self, 'vertex_credentials') and self.vertex_credentials:
                completion_params.update({
                    "vertex_credentials": json.dumps(self.vertex_credentials),
                    "vertex_project": self.vertex_project,
                    "vertex_location": self.vertex_location
                })
            elif self.model_name.startswith("bedrock/"):
                completion_params["aws_region_name"] = self.aws_region
            elif self.model_name.startswith("azure/"):
                completion_params.update({
                    "api_base": self.azure_api_base,
                    "api_key": self.azure_api_key,
                    "api_version": self.azure_api_version
                })
            
            response = completion(**completion_params)
            result = response.choices[0].message.content
            logger.llm_response(result)
            
            return result

        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}")
            raise

