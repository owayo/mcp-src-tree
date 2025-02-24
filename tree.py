import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional

import pathspec
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("src-tree")


def read_gitignore(base_path: str) -> Optional[pathspec.PathSpec]:
    """
    Read .gitignore file and return a PathSpec object

    Args:
        base_path: Base directory path containing .gitignore

    Returns:
        PathSpec object, or None if .gitignore doesn't exist
    """
    gitignore_path = os.path.join(base_path, ".gitignore")
    if not os.path.exists(gitignore_path):
        return None

    with open(gitignore_path, "r") as f:
        # Remove empty lines and comments
        lines = [
            line.strip()
            for line in f.readlines()
            if line.strip() and not line.startswith("#")
        ]
        gitignore = pathspec.PathSpec.from_lines(
            pathspec.patterns.GitWildMatchPattern, lines
        )
    return gitignore


def should_ignore(
    path: str, base_path: str, gitignore: Optional[pathspec.PathSpec] = None
) -> bool:
    """
    Determine if the specified path should be ignored

    Args:
        path: Path to check
        base_path: Base directory path containing .gitignore
        gitignore: PathSpec object from .gitignore

    Returns:
        True if path should be ignored
    """
    # Ignore directories starting with .
    if os.path.isdir(path) and os.path.basename(path).startswith("."):
        return True

    # Check if path matches .gitignore rules
    if gitignore:
        relative_path = os.path.relpath(path, base_path)
        # Add trailing slash for directories
        if os.path.isdir(path):
            relative_path = relative_path + os.sep
        # Normalize path (unify slashes)
        relative_path = relative_path.replace(os.sep, "/")
        if gitignore.match_file(relative_path):
            return True

    return False


def build_tree(
    path: str,
    base_path: str,
    gitignore: Optional[pathspec.PathSpec] = None,
    is_root: bool = True,
) -> Dict[str, Any]:
    """
    Build directory tree structure

    Args:
        path: Directory path to traverse
        base_path: Base directory path containing .gitignore
        gitignore: PathSpec object from .gitignore
        is_root: Whether this is the root directory

    Returns:
        Dictionary representing directory tree
    """
    # Check if path should be ignored
    if should_ignore(path, base_path, gitignore):
        return None

    name = os.path.abspath(path) if is_root else os.path.basename(path)

    if os.path.isfile(path):
        return {"name": name, "type": "file"}

    result = {"name": name, "type": "directory", "children": []}

    try:
        items = os.listdir(path)
        for item in sorted(items):
            item_path = os.path.join(path, item)
            child = build_tree(item_path, base_path, gitignore, is_root=False)
            if child:
                result["children"].append(child)
    except PermissionError:
        pass

    return result


@mcp.prompt()
async def src_tree(directory: str) -> str:
    """
    Get file tree as JSON string

    Returns:
        JSON string representing the file tree
    """
    if not os.path.exists(directory):
        return json.dumps({"error": "directory not found"}, indent=2)

    gitignore = read_gitignore(directory)
    tree = build_tree(directory, directory, gitignore)

    return json.dumps(tree, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_src_tree(directory: str) -> str:
    """
    Generate a file tree for the specified directory, filtering files based on .gitignore.
    Traverses the filesystem and generates a JSON-formatted tree structure that preserves hierarchy.
    """
    if not os.path.exists(directory):
        return json.dumps({"error": "directory not found"}, indent=2)

    gitignore = read_gitignore(directory)
    tree = build_tree(directory, directory, gitignore)

    return json.dumps(tree, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        mcp.run(transport="stdio")
    elif args[0] == "test" and len(args) == 2:
        # Create event loop to run async function
        result = asyncio.run(get_src_tree(args[1]))
        print(result)
