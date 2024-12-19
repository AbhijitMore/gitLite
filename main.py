import os
import hashlib
import pickle
import argparse
from typing import List, Dict, Union


# Define types for easier readability
Blob = bytes  # A blob is a binary data object, such as a file's contents
Tree = Dict[str, Union['Tree', Blob]]  # A tree is a directory structure, which can contain other trees or blobs
Object = Union[Blob, Tree, 'Commit']  # An object can be a blob, a tree, or a commit

# Path constants
GITLITE_DIR = ".gitLite"
OBJECTS_DIR = os.path.join(GITLITE_DIR, "objects")
REFS_DIR = os.path.join(GITLITE_DIR, "refs", "heads")
INDEX_PATH = os.path.join(GITLITE_DIR, "index")
HEAD_PATH = os.path.join(GITLITE_DIR, "HEAD")


def init():
    """
    Initializes a gitLite repository.

    This function:
    - Creates the necessary directory structure for a gitLite repository.
    - Initializes the main reference (`HEAD`) pointing to the `main` branch.
    
    If a gitLite repository already exists, it informs the user and does nothing.
    """
    if os.path.exists(GITLITE_DIR):
        print("gitLite repository already exists.")
        return
    
    # Create the necessary directories for a gitLite repository
    os.makedirs(OBJECTS_DIR)
    os.makedirs(REFS_DIR)
    
    # Initialize the HEAD file to point to the main branch
    with open(HEAD_PATH, "w") as f:
        f.write("ref: refs/heads/main") 
    
    print("gitLite repository initialized.")


def read_gitliteignore() -> List[str]:
    """
    Reads the .gitLiteignore file (if it exists) and returns a list of patterns
    to ignore in the working directory.
    """
    ignored_files = []
    if os.path.exists(".gitLiteignore"):
        with open(".gitLiteignore", "r") as f:
            ignored_files = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
    return ignored_files


def hash_file(file_path: str) -> str:
    """
    Hash a file's content and return the hex digest.
    """
    hasher = hashlib.sha1()  # Using SHA-1 as Git does
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):  # Read file in chunks
            hasher.update(chunk)
    return hasher.hexdigest()


def load_index() -> Dict[str, str]:
    """
    Load the staging area (index). The index stores a map of file paths to their content hashes.
    """
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, 'rb') as f:
            return pickle.load(f)
    return {}


def save_index(index: Dict[str, str]):
    """
    Save the staging area (index) to disk.
    """
    with open(INDEX_PATH, 'wb') as f:
        pickle.dump(index, f)


def add(files: List[str]):
    """
    Add files to the staging area (index).
    The staged files are added with their content hash as an identifier.
    """
    # Load the current index (staging area)
    index = load_index()

    # Get ignored files from .gitLiteignore
    ignored_files = read_gitliteignore()

    # Add the files to the staging area
    for file_path in files:
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} does not exist.")
            continue

        # Skip directories
        if os.path.isdir(file_path):
            print(f"Warning: {file_path} is a directory, not a file.")
            continue

        # Ignore files listed in .gitLiteignore
        if any([file_path.startswith(ignored) for ignored in ignored_files]):
            print(f"Warning: {file_path} is ignored due to .gitLiteignore.")
            continue

        # Compute the hash of the file
        file_hash = hash_file(file_path)
        
        # If the file is already staged, check if the hash is different (i.e., the file was modified)
        if file_path in index and index[file_path] != file_hash:
            print(f"File {file_path} has been modified, updating the staging area.")

            index[file_path] = file_hash
            print(f"Added {file_path} to the staging area.")
        
        else:
            "File is up to date."
        
        index[file_path] = file_hash
    # Save the updated index back to disk
    save_index(index)

def status():
    """Show the current status of the gitLite repository."""
    if not os.path.exists(GITLITE_DIR):
        print("No gitLite repository found. Please run 'gitLite init' to initialize a repository.")
        return
    
    # Check if HEAD exists
    if not os.path.exists(HEAD_PATH):
        print("No HEAD file found. The repository may not have been initialized correctly.")
        return
    
    with open(HEAD_PATH, "r") as f:
        head_ref = f.read().strip()
    
    if head_ref.startswith("ref: "):
        branch_ref = head_ref[5:]
        branch_ref_path = os.path.join(GITLITE_DIR, branch_ref)
        
        if os.path.exists(branch_ref_path):
            with open(branch_ref_path, "r") as f:
                current_commit_hash = f.read().strip()
            print(f"On branch 'main'. Last commit: {current_commit_hash}")
        else:
            print("No commits found yet.")
    else:
        print("HEAD is not pointing to a valid reference.")

    # Simulate the "Your branch is up to date with 'origin/main'" message (no remote for now)
    print("Your branch is up to date with 'origin/main'.")
    
    # Check for staged files (files in the index)
    index = load_index()
    staged_files = list(index.keys())

    if staged_files:
        print("\nStaged files:")
        for file in staged_files:
            # Check if the file has been modified
            file_hash = index[file]
            current_file_hash = hash_file(file)  # Compute current hash of the file
            if file_hash != current_file_hash:
                print(f"        {file} (modified)")
            else:
                print(f"        {file}")
    else:
        print("\nNo files staged for commit.")

    # Get untracked files
    untracked_files = get_untracked_files()
    
    if untracked_files:
        print("\nUntracked files:")
        print("  (use \"git add <file>...\" to include in what will be committed)")
        for file in untracked_files:
            print(f"        {file}")
        print("\nNothing added to commit but untracked files present (use \"git add\" to track)")
    else:
        print("\nNothing to commit, working tree clean.")

def get_untracked_files() -> List[str]:
    """
    Get a list of files that are in the working directory but not tracked by gitLite.
    These files are not yet added to the repository or staged for commit.
    """
    # Load the index to know which files are staged
    index = load_index()
    tracked_files = set(index.keys())  # Files that are tracked (i.e., staged)

    ignored_files = read_gitliteignore()
    untracked_files = []
    
    for root, dirs, files in os.walk("."):
        # Exclude .gitLite directory and files that match .gitLiteignore patterns
        if root == GITLITE_DIR:
            continue
        
        for file in files:
            relative_path = os.path.relpath(os.path.join(root, file), start=".")
            
            # Skip ignored files
            if any([relative_path.startswith(ignored) for ignored in ignored_files]):
                continue
            
            # If file is not tracked (i.e., not staged), add it to untracked list
            if relative_path not in tracked_files:
                untracked_files.append(relative_path)
    
    return untracked_files

def commit():
    pass

def log():
    pass

def checkout():
    pass

def diff():
    pass


# Main program entry point
def main():
    """CLI Interface for gitLite."""
    parser = argparse.ArgumentParser(description="gitLite: A Simple Git Implementation")
    
    # Subparsers for different commands
    subparsers = parser.add_subparsers(dest="command")

    # 'init' command: Initialize a new repository
    subparsers.add_parser("init", help="Initialize a new repository")

    # 'status' command: Show the status of the repository
    subparsers.add_parser("status", help="Show the status of the repository")

    # 'add' command: Add files to the staging area
    add_parser = subparsers.add_parser("add", help="Add files to the staging area")
    add_parser.add_argument("files", nargs="+", help="Files to add")

    # 'commit' command: Commit the staged changes with a commit message
    commit_parser = subparsers.add_parser("commit", help="Commit the staged changes")
    commit_parser.add_argument("-m", "--message", required=True, help="Commit message")

    # 'log' command: Show commit logs
    subparsers.add_parser("log", help="Show commit logs")

    # 'checkout' command: Switch to a specific commit
    checkout_parser = subparsers.add_parser("checkout", help="Switch to a commit")
    checkout_parser.add_argument("commit", help="Commit to switch to")

    # 'diff' command: Show differences between working directory and the index (staging area)
    subparsers.add_parser("diff", help="Show differences between the working directory and the index")

    # Parse the arguments from the command line
    args = parser.parse_args()

    # Execute the corresponding function based on the command
    if args.command == "init":
        init()
    elif args.command == "status":
        status()
    elif args.command == "add":
        add(args.files)
    elif args.command == "commit":
        commit(args.message)
    elif args.command == "log":
        log()
    elif args.command == "checkout":
        checkout(args.commit)
    elif args.command == "diff":
        diff()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
