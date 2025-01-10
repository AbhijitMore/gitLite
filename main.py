import os
import hashlib
import pickle
import argparse
import time
import difflib
import shutil
from typing import List, Dict, Union

Blob = bytes
Tree = Dict[str, Union['Tree', Blob]]
Object = Union[Blob, Tree, 'Commit']

GITLITE_DIR = ".gitLite"
OBJECTS_DIR = os.path.join(GITLITE_DIR, "objects")
REFS_DIR = os.path.join(GITLITE_DIR, "refs", "heads")
INDEX_PATH = os.path.join(GITLITE_DIR, "index")
HEAD_PATH = os.path.join(GITLITE_DIR, "HEAD")


class Commit:
    def __init__(self, message: str, tree_hash: str, parent_commit: Union[str, None]):
        self.message = message
        self.tree_hash = tree_hash
        self.parent_commit = parent_commit
        self.timestamp = time.time()

    def serialize(self) -> bytes:
        return pickle.dumps(self)


def init():
    if os.path.exists(GITLITE_DIR):
        print("gitLite repository already exists.")
        return

    os.makedirs(OBJECTS_DIR)
    os.makedirs(REFS_DIR)

    with open(HEAD_PATH, "w") as f:
        f.write("ref: refs/heads/main")

    print("gitLite repository initialized.")


def read_gitliteignore() -> List[str]:
    ignored_files = []
    if os.path.exists(".gitLiteignore"):
        with open(".gitLiteignore", "r") as f:
            ignored_files = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
    return ignored_files


def hash_file(file_path: str) -> str:
    hasher = hashlib.sha1()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_index() -> Dict[str, str]:
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, 'rb') as f:
            return pickle.load(f)
    return {}


def save_index(index: Dict[str, str]):
    with open(INDEX_PATH, 'wb') as f:
        pickle.dump(index, f)


def get_untracked_files() -> List[str]:
    index = load_index()
    tracked_files = set(index.keys())

    ignored_files = read_gitliteignore()
    untracked_files = []

    for root, dirs, files in os.walk("."):
        if root == GITLITE_DIR:
            continue

        for file in files:
            relative_path = os.path.relpath(os.path.join(root, file), start=".")

            if any([relative_path.startswith(ignored) for ignored in ignored_files]):
                continue

            if relative_path not in tracked_files:
                untracked_files.append(relative_path)

    return untracked_files


def add(files: List[str]):
    index = load_index()

    ignored_files = read_gitliteignore()

    for file_path in files:
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} does not exist.")
            continue

        if os.path.isdir(file_path):
            print(f"Warning: {file_path} is a directory, not a file.")
            continue

        if any([file_path.startswith(ignored) for ignored in ignored_files]):
            print(f"Warning: {file_path} is ignored due to .gitLiteignore.")
            continue

        file_hash = hash_file(file_path)
        object_dir = os.path.join(OBJECTS_DIR, file_hash[:2])
        os.makedirs(object_dir, exist_ok=True)
        blob_path = os.path.join(object_dir, file_hash[2:])

        if not os.path.exists(blob_path):
            with open(blob_path, 'wb') as f:
                with open(file_path, 'rb') as file:
                    f.write(file.read())

        if file_path not in index or index[file_path] != file_hash:
            index[file_path] = file_hash
            print(f"Added {file_path} to the staging area.")

    save_index(index)


def status():
    if not os.path.exists(GITLITE_DIR):
        print("No gitLite repository found. Please run 'gitLite init' to initialize a repository.")
        return

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

    print("Your branch is up to date with 'origin/main'.")

    index = load_index()
    staged_files = list(index.keys())

    if staged_files:
        print("\nStaged files:")
        for file in staged_files:
            file_hash = index[file]
            current_file_hash = hash_file(file)
            if file_hash != current_file_hash:
                print(f"        {file} (modified)")
            else:
                print(f"        {file}")
    else:
        print("\nNo files staged for commit.")

    untracked_files = get_untracked_files()

    if untracked_files:
        print("\nUntracked files:")
        print("  (use \"git add <file>...\" to include in what will be committed)")
        for file in untracked_files:
            print(f"        {file}")
        print("\nNothing added to commit but untracked files present (use \"git add\" to track)")
    else:
        print("\nNothing to commit, working tree clean.")


def build_tree(index: Dict[str, str]) -> Tree:
    tree = {}
    for file_path, file_hash in index.items():
        object_dir = os.path.join(OBJECTS_DIR, file_hash[:2])
        blob_path = os.path.join(object_dir, file_hash[2:])

        if os.path.exists(blob_path):
            with open(blob_path, 'rb') as f:
                blob = f.read()
            tree[file_path] = blob
        else:
            print(f"Error: Blob for {file_path} not found.")

    return tree


def commit(message: str):
    index = load_index()

    if not index:
        print("No files staged for commit.")
        return

    tree = build_tree(index)

    tree_hash = hashlib.sha1(pickle.dumps(tree)).hexdigest()
    tree_path = os.path.join(OBJECTS_DIR, tree_hash[:2], tree_hash[2:])

    if not os.path.exists(tree_path):
        os.makedirs(os.path.dirname(tree_path), exist_ok=True)
        with open(tree_path, 'wb') as f:
            f.write(pickle.dumps(tree))

    parent_commit = None
    if os.path.exists(HEAD_PATH):
        with open(HEAD_PATH, 'r') as f:
            head_ref = f.read().strip()
        if head_ref.startswith("ref: "):
            branch_ref = head_ref[5:]
            branch_ref_path = os.path.join(GITLITE_DIR, branch_ref)
            if os.path.exists(branch_ref_path):
                with open(branch_ref_path, 'r') as f:
                    parent_commit = f.read().strip()

    commit_obj = Commit(message, tree_hash, parent_commit)
    commit_hash = hashlib.sha1(commit_obj.serialize()).hexdigest()
    commit_path = os.path.join(OBJECTS_DIR, commit_hash[:2], commit_hash[2:])

    if not os.path.exists(commit_path):
        os.makedirs(os.path.dirname(commit_path), exist_ok=True)
        with open(commit_path, 'wb') as f:
            f.write(commit_obj.serialize())

    with open(HEAD_PATH, 'w') as f:
        f.write(f"ref: refs/heads/main")

    with open(os.path.join(REFS_DIR, "main"), 'w') as f:
        f.write(commit_hash)

    save_index({})

    print(f"Commit {commit_hash} created successfully.")


def log():
    if not os.path.exists(HEAD_PATH):
        print("No HEAD file found.")
        return

    with open(HEAD_PATH, 'r') as f:
        head_ref = f.read().strip()

    if head_ref.startswith("ref: "):
        branch_ref = head_ref[5:]
        branch_ref_path = os.path.join(GITLITE_DIR, branch_ref)

        if os.path.exists(branch_ref_path):
            with open(branch_ref_path, 'r') as f:
                current_commit_hash = f.read().strip()

            print("Commit history:\n")
            while current_commit_hash:
                commit_path = os.path.join(OBJECTS_DIR, current_commit_hash[:2], current_commit_hash[2:])
                with open(commit_path, 'rb') as f:
                    commit = pickle.load(f)

                print(f"Commit {current_commit_hash}: {commit.message}")
                if commit.parent_commit:
                    current_commit_hash = commit.parent_commit
                else:
                    break
        else:
            print("No commits found yet.")
    else:
        print("HEAD is not pointing to a valid reference.")


def checkout(commit_hash: str):
    commit_path = os.path.join(OBJECTS_DIR, commit_hash[:2], commit_hash[2:])

    if not os.path.exists(commit_path):
        print(f"Error: Commit {commit_hash} not found.")
        return

    with open(commit_path, 'rb') as f:
        commit = pickle.load(f)

    tree_hash = commit.tree_hash
    tree_path = os.path.join(OBJECTS_DIR, tree_hash[:2], tree_hash[2:])

    if not os.path.exists(tree_path):
        print(f"Error: Tree {tree_hash} not found.")
        return

    with open(tree_path, 'rb') as f:
        tree = pickle.load(f)

    update_working_directory(tree)

    with open(HEAD_PATH, 'w') as f:
        f.write(f"ref: refs/heads/main")

    with open(os.path.join(REFS_DIR, "main"), 'w') as f:
        f.write(commit_hash)

    print(f"Checked out commit {commit_hash} successfully.")


def update_working_directory(tree: Tree, base_path: str = "."):
    for entry, value in tree.items():
        full_path = os.path.join(base_path, entry)

        if isinstance(value, bytes):
            with open(full_path, 'wb') as f:
                f.write(value)
            print(f"Restored file: {full_path}")

        elif isinstance(value, dict):
            os.makedirs(full_path, exist_ok=True)
            print(f"Restored directory: {full_path}")
            update_working_directory(value, full_path)


def diff():
    index = load_index()

    if not index:
        print("No staged files.")
        return

    untracked_files = get_untracked_files()

    for staged_file in index.keys():
        if os.path.exists(staged_file):
            staged_file_hash = index[staged_file]
            staged_file_path = os.path.join(OBJECTS_DIR, staged_file_hash[:2], staged_file_hash[2:])

            if os.path.exists(staged_file_path):
                with open(staged_file_path, 'rb') as f:
                    staged_content = f.read().decode('utf-8', 'ignore').splitlines()
                    print(f"Staged content for {staged_file}:")
                    print(staged_content)

                with open(staged_file, 'r') as f:
                    working_content = f.readlines()
                    print(f"Working directory content for {staged_file}:")
                    print(working_content)

                diff = difflib.unified_diff(working_content, staged_content,
                                            fromfile=f"Staged: {staged_file}",
                                            tofile=f"Working: {staged_file}")
                print('\n'.join(diff))

    if untracked_files:
        print("\nUntracked files:")
        for file in untracked_files:
            print(f"        {file}")


def main():
    parser = argparse.ArgumentParser(description="gitLite: A Simple Git Implementation")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Initialize a new repository")
    subparsers.add_parser("status", help="Show the status of the repository")

    add_parser = subparsers.add_parser("add", help="Add files to the staging area")
    add_parser.add_argument("files", nargs="+", help="Files to add")

    commit_parser = subparsers.add_parser("commit", help="Commit the staged changes")
    commit_parser.add_argument("-m", "--message", required=True, help="Commit message")

    subparsers.add_parser("log", help="Show commit logs")

    checkout_parser = subparsers.add_parser("checkout", help="Switch to a commit")
    checkout_parser.add_argument("commit", help="Commit to switch to")

    subparsers.add_parser("diff", help="Show differences between the working directory and the index")

    args = parser.parse_args()

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
