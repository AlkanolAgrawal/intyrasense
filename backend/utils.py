"""
Utility Functions
Helper functions for document management and file operations.
"""

import os

RAW_DIR = "data/raw_docs"

def list_documents():
    if not os.path.exists(RAW_DIR):
        return []
        # Return sorted list of filenames
    return sorted(os.listdir(RAW_DIR))
