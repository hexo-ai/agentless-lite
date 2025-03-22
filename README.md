# Setup Guid

### Cloning the Repository

```bash
git clone https://github.com/yogendrahexo/agentless-lite.git
cd agentless-lite
```

## Installation

### Using Conda

To create a Conda environment using the `environment.yaml` file, run the following commands:

```bash
conda env create -f environment.yaml
conda activate agentless-lite
```

### Using Virtualenv

Alternatively, you can create a virtual environment using `venv`:

```bash
python -m venv agentless-venv
source agentless-venv/bin/activate  # On Windows use `agentless-venv\Scripts\activate`
pip install -r requirements.txt
```

## AWS Credentials Setup

Before running the tool, ensure that your AWS credentials are set up in the environment. You can do this by exporting your AWS access key and secret key:

```bash
export AWS_ACCESS_KEY_ID=your_access_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_access_key
```

Replace `your_access_key_id` and `your_secret_access_key` with your actual AWS credentials.

## Azure OpenAI Credentials Setup

When using Azure OpenAI, create a `.env` file in the root directory with the following variables:

```bash
AZURE_OPENAI_API_KEY=your_azure_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com
AZURE_OPENAI_API_VERSION=2023-05-15
AZURE_DEPLOYMENT_NAME=your_deployment_name
```

Replace these values with your actual Azure OpenAI credentials.

## Vertex AI Credentials Setup

When using Vertex AI, you need a Google Cloud service account key:

1. Create a service account in Google Cloud Console
2. Generate a JSON key for this service account
3. Place this JSON file in the root directory as `security-key.json` or specify a custom path in the code

Example service account key structure:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\nYour-Private-Key\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@your-project-id.iam.gserviceaccount.com",
  "client_id": "client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project-id.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
```

## LLM Provider Configurations

The system supports multiple LLM providers through the `LLMInterface` class. Below are configuration examples for each supported provider:

### Google Vertex AI (Currently Active)

```python
llm = LLMInterface(
    model_name="vertex_ai/claude-3-7-sonnet@20250219",
    temperature=0.1,
    max_tokens=4096,
    security_key_path="security-key.json",
    vertex_location="us-east5"
)
```

### AWS Bedrock

```python
llm = LLMInterface(
    model_name="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
    temperature=0.1,
    max_tokens=4096,
    aws_region="us-west-2"
)
```

### Azure OpenAI

```python
llm = LLMInterface(
    model_name=f"azure/{os.getenv('AZURE_DEPLOYMENT_NAME')}",
    temperature=0.1,
    max_tokens=4096,
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION")
)
```

To switch between providers, uncomment the desired configuration in the `find_patch` function in `run.py` and comment out the others.

## Basic Usage

The basic usage pattern is demonstrated:

```
from run import find_patch

def main():
    # Test app arguments
    bug_description = "There is a bug in the get_cart_total endpoint where it randomly skips items during total calculation."
    project_dir = "test-app"

    # Run find_patch and get the result
    patch = find_patch(
        bug_description=bug_description,
        project_dir=project_dir
    )

    # Print the results
    print("\nGenerated Patch:")
    print("=" * 50)
    if patch:
        print(patch)
    else:
        print("No patch was generated")
    print("=" * 50)

if __name__ == "__main__":
    main()
```

### Running with Command-Line Arguments

You can run the tool directly using `run.py` with command-line arguments:

```bash
python run.py --bug_description "Description of the bug to fix" --project_dir "path/to/project" --instance_id "instance_id"
```

For example:

```bash
python run.py --bug_description "There is a bug in the login function where it doesn't validate the email format" --project_dir "my-web-app" --instance_id "my-web-app-try1"
```

The command-line arguments are:

- `--bug_description`: Description of the bug to fix (default: "There is a bug in the get_cart_total endpoint where it randomly skips items during total calculation.")
- `--project_dir`: Directory containing the project to fix (default: "test-app")
- `--instance_id`: Instance ID for this bug fix attempt, if not provided, a new instance ID will be generated

If you don't provide these arguments, the script will use the default values.

### Key Components

1. **find_patch Function in the run.py**
   - Main entry point for bug fixing
   - Parameters:
     - `bug_description`: String describing the bug
     - `project_dir`: Path to the project directory containing the code

### Running SWE-bench or SWE-gym

To run SWE-bench or SWE-gym, use the `process-swegym.py` script. This script takes two optional arguments:

- `--instance-id`: The specific instance ID to process.
- `--n`: The number of instances to process. If not specified, all instances will be processed.

The dataset to be used (SWE-bench or SWE-gym) can be set on line 245 of `process-swegym.py`. It is currently set to SWE-gym.

### Architecture

![Screenshot from 2025-03-05 17-58-59](https://github.com/user-attachments/assets/ae8d6f54-e190-4d65-869c-7a2497f15b84)
