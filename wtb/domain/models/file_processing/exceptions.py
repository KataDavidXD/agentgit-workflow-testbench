"""
File Processing Exceptions.

Custom exceptions for file processing domain operations.
Follows exception hierarchy pattern for precise error handling.

Design Principles:
- Single Responsibility: One file for all file processing exceptions
- Hierarchy: All inherit from FileProcessingError base
- Rich context: Exceptions carry relevant data
"""


class FileProcessingError(Exception):
    """
    Base exception for file processing errors.
    
    All file processing exceptions inherit from this.
    Allows catching all file processing errors with one handler.
    """
    pass


class DuplicateFileError(FileProcessingError):
    """
    Attempted to add duplicate file to commit.
    
    Raised when adding a file path that already exists in the commit.
    Enforces commit invariant: no duplicate paths.
    """
    pass


class InvalidBlobIdError(FileProcessingError):
    """
    Invalid blob ID format.
    
    Raised when BlobId validation fails:
    - Not a string
    - Not 64 characters
    - Not hexadecimal
    """
    pass


class InvalidCommitIdError(FileProcessingError):
    """
    Invalid commit ID format.
    
    Raised when CommitId validation fails:
    - Not a string
    - Not a valid UUID
    """
    pass


class CommitAlreadyFinalized(FileProcessingError):
    """
    Commit has already been finalized and cannot be modified.
    
    Raised when attempting to:
    - Add memento to finalized commit
    - Finalize an already finalized commit
    """
    pass


__all__ = [
    "FileProcessingError",
    "DuplicateFileError",
    "InvalidBlobIdError",
    "InvalidCommitIdError",
    "CommitAlreadyFinalized",
]
