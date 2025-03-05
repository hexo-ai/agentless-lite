#!/usr/bin/env python3
import argparse
import subprocess
import os

def main():
    parser = argparse.ArgumentParser(description='Apply git diff to files')
    parser.add_argument('--dir', default='/home/ubuntu/hexo/new/Agentless/standalone-agentless/test-app copy', help='Target directory (default: current directory)')
    
    args = parser.parse_args()
    
    # Get absolute paths
    current_dir = os.path.abspath(args.dir)
    patch_path = os.path.join(current_dir, 'patch.diff')
    
    # Make sure we're in a git repository
    try:
        subprocess.run(['git', 'rev-parse', '--git-dir'], 
                      check=True, 
                      capture_output=True,
                      cwd=current_dir)
    except subprocess.CalledProcessError:
        subprocess.run(['git', 'init'], check=True, cwd=current_dir)
    
    # Add files to git if they're not tracked
    subprocess.run(['git', 'add', '.'], check=True, cwd=current_dir)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], 
                  check=True, 
                  cwd=current_dir,
                  env={'GIT_AUTHOR_NAME': 'Bot', 
                       'GIT_AUTHOR_EMAIL': 'bot@example.com',
                       'GIT_COMMITTER_NAME': 'Bot',
                       'GIT_COMMITTER_EMAIL': 'bot@example.com'})
    
    # Apply the patch
    try:
        result = subprocess.run(['git', 'apply', '--verbose', patch_path], 
                              check=True, 
                              capture_output=True, 
                              text=True,
                              cwd=current_dir)
        print("Successfully applied patch")
        if result.stdout:
            print("Output:", result.stdout)
        if result.stderr:
            print("Details:", result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Failed to apply patch: {e.stderr}")

if __name__ == '__main__':
    main()