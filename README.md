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

## Basic Usage

The basic usage pattern is demonstrated:

```
from main import find_patch

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

### Key Components

1. **find_patch Function**
   - Main entry point for bug fixing
   - Parameters:
     - `bug_description`: String describing the bug
     - `project_dir`: Path to the project directory containing the code

### Architecture
