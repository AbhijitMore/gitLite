import pickle
from typing import Union, Dict
import time

class Commit:
    def __init__(self, message: str, tree_hash: str, parent_commit: Union[str, None]):
        self.message = message
        self.tree_hash = tree_hash
        self.parent_commit = parent_commit
        self.timestamp = time.time()

    def serialize(self) -> bytes:
        return pickle.dumps(self)
    
Tree = Dict[str, Union['Tree', bytes]]
