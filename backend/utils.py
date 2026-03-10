"""
Utility Functions
Helper functions for document management and file operations.
"""

import os

RAW_DIR = "data/raw_docs"

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


def list_documents():
    if not os.path.exists(RAW_DIR):
        return []

    files = []

    for f in os.listdir(RAW_DIR):
        ext = os.path.splitext(f)[1].lower()

        if ext in ALLOWED_EXTENSIONS:
            files.append(f)

    return sorted(files)