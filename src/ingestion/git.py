import os
import git
from src.database.models import Repository

def git_clone(repo_url: str, destination_path: str):
    try:
        git.Repo.clone_from(repo_url, destination_path)
    except Exception as e:
        print(f"Error cloning repository: {e}")
        raise

def git_extract_metadata(destination_path: str, repo: Repository):
    try:
        repo_git = git.Repo(destination_path)
        name = repo.url.rstrip('/').split('/')[-1].removesuffix('.git')
        
        # Count non-git files
        filecount = 0
        for root, dirs, files in os.walk(destination_path):
            if '.git' in dirs:
                dirs.remove('.git')
            filecount += len(files)
            
        try:
            default_branch = repo_git.active_branch.name
        except Exception:
            default_branch = "main"

        clone_path = destination_path
        return name, filecount, default_branch, clone_path
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        raise
