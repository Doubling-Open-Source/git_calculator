"""
Multi-Repository Manager for Git Calculator

This module provides functionality to analyze multiple Git repositories
and aggregate their metrics for comparative analysis.
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging
from contextlib import contextmanager
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class RepositoryInfo:
    """Information about a repository to analyze."""
    name: str
    path: str
    url: Optional[str] = None
    branch: Optional[str] = None
    description: Optional[str] = None


class MultiRepoManager:
    """
    Manages multiple Git repositories for analysis.
    
    This class handles cloning, updating, and organizing multiple repositories
    for comparative analysis.
    """
    
    def __init__(self, workspace_dir: Optional[str] = None):
        """
        Initialize the multi-repository manager.
        
        Args:
            workspace_dir: Directory to store cloned repositories.
                          If None, uses a temporary directory.
        """
        if workspace_dir:
            self.workspace_dir = Path(workspace_dir)
        else:
            self.workspace_dir = Path(tempfile.mkdtemp(prefix="git_calc_multi_"))
        
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.repositories: Dict[str, RepositoryInfo] = {}
        
        logger.info(f"Multi-repo manager initialized with workspace: {self.workspace_dir}")
    
    def add_repository(self, 
                      name: str, 
                      path_or_url: str, 
                      branch: Optional[str] = None,
                      description: Optional[str] = None) -> bool:
        """
        Add a repository to the analysis set.
        
        Args:
            name: Unique name for the repository
            path_or_url: Local path or Git URL
            branch: Specific branch to analyze (optional)
            description: Optional description
            
        Returns:
            bool: True if successfully added, False otherwise
        """
        try:
            if name in self.repositories:
                logger.warning(f"Repository '{name}' already exists. Updating...")
            
            # Determine if it's a URL or local path
            if path_or_url.startswith(('http://', 'https://', 'git@', 'ssh://')):
                # It's a URL - we'll clone it
                repo_info = RepositoryInfo(
                    name=name,
                    path=str(self.workspace_dir / name),
                    url=path_or_url,
                    branch=branch,
                    description=description
                )
            else:
                # It's a local path
                local_path = Path(path_or_url).resolve()
                if not local_path.exists():
                    logger.error(f"Local path does not exist: {local_path}")
                    return False
                
                repo_info = RepositoryInfo(
                    name=name,
                    path=str(local_path),
                    url=None,
                    branch=branch,
                    description=description
                )
            
            self.repositories[name] = repo_info
            logger.info(f"Added repository '{name}': {path_or_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add repository '{name}': {e}")
            return False
    
    def clone_repositories(self) -> Dict[str, bool]:
        """
        Clone all remote repositories to the workspace.
        
        Returns:
            Dict mapping repository names to success status
        """
        results = {}
        
        for name, repo_info in self.repositories.items():
            if repo_info.url:
                try:
                    repo_path = Path(repo_info.path)
                    
                    if repo_path.exists():
                        logger.info(f"Repository '{name}' already exists at {repo_path}")
                        results[name] = True
                        continue
                    
                    # Clone the repository
                    cmd = ['git', 'clone']
                    if repo_info.branch:
                        cmd.extend(['-b', repo_info.branch])
                    cmd.extend([repo_info.url, str(repo_path)])
                    
                    logger.info(f"Cloning {repo_info.url} to {repo_path}")
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    
                    results[name] = True
                    logger.info(f"Successfully cloned repository '{name}'")
                    
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to clone repository '{name}': {e.stderr}")
                    results[name] = False
                except Exception as e:
                    logger.error(f"Unexpected error cloning repository '{name}': {e}")
                    results[name] = False
            else:
                # Local repository - just verify it exists
                if Path(repo_info.path).exists():
                    results[name] = True
                else:
                    logger.error(f"Local repository path does not exist: {repo_info.path}")
                    results[name] = False
        
        return results
    
    def update_repositories(self) -> Dict[str, bool]:
        """
        Update all cloned repositories (git pull).
        
        Returns:
            Dict mapping repository names to success status
        """
        results = {}
        
        for name, repo_info in self.repositories.items():
            if repo_info.url:  # Only update cloned repositories
                try:
                    repo_path = Path(repo_info.path)
                    if not repo_path.exists():
                        logger.warning(f"Repository path does not exist: {repo_path}")
                        results[name] = False
                        continue
                    
                    # Change to repository directory and pull
                    cmd = ['git', 'pull']
                    if repo_info.branch:
                        cmd.extend(['origin', repo_info.branch])
                    
                    logger.info(f"Updating repository '{name}'")
                    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, check=True)
                    
                    results[name] = True
                    logger.info(f"Successfully updated repository '{name}'")
                    
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to update repository '{name}': {e.stderr}")
                    results[name] = False
                except Exception as e:
                    logger.error(f"Unexpected error updating repository '{name}': {e}")
                    results[name] = False
            else:
                # Local repository - no update needed
                results[name] = True
        
        return results
    
    def get_repository_paths(self) -> Dict[str, str]:
        """
        Get all repository paths.
        
        Returns:
            Dict mapping repository names to their paths
        """
        return {name: repo.path for name, repo in self.repositories.items()}
    
    def list_repositories(self) -> List[RepositoryInfo]:
        """
        List all added repositories.
        
        Returns:
            List of RepositoryInfo objects
        """
        return list(self.repositories.values())
    
    def remove_repository(self, name: str) -> bool:
        """
        Remove a repository from the analysis set.
        
        Args:
            name: Name of the repository to remove
            
        Returns:
            bool: True if successfully removed, False otherwise
        """
        if name in self.repositories:
            del self.repositories[name]
            logger.info(f"Removed repository '{name}'")
            return True
        else:
            logger.warning(f"Repository '{name}' not found")
            return False
    
    def cleanup(self):
        """Clean up the workspace directory."""
        if self.workspace_dir.exists() and str(self.workspace_dir).startswith('/tmp'):
            shutil.rmtree(self.workspace_dir)
            logger.info(f"Cleaned up workspace directory: {self.workspace_dir}")
    
    @contextmanager
    def repository_context(self, repo_name: str):
        """
        Context manager to temporarily change to a repository directory.
        
        Args:
            repo_name: Name of the repository
            
        Yields:
            Path: Path to the repository
        """
        if repo_name not in self.repositories:
            raise ValueError(f"Repository '{repo_name}' not found")
        
        repo_path = Path(self.repositories[repo_name].path)
        original_cwd = os.getcwd()
        
        try:
            os.chdir(repo_path)
            yield repo_path
        finally:
            os.chdir(original_cwd)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
    
    def __repr__(self):
        return f"MultiRepoManager(workspace={self.workspace_dir}, repos={len(self.repositories)})"
