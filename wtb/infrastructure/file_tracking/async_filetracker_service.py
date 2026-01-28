
import aiofiles
import aiofiles.os
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
import logging

from wtb.domain.interfaces.async_file_tracking import IAsyncFileTrackingService, FileTrackingResult
from wtb.domain.interfaces.async_unit_of_work import IAsyncUnitOfWork
from wtb.domain.models.file_processing import FileMemento, FileCommit, CheckpointFileLink, BlobId, CommitId

logger = logging.getLogger(__name__)

class AsyncFileTrackerService(IAsyncFileTrackingService):
    """
    Async File Tracking Service using Repository Pattern.
    
    ARCHITECTURE ALIGNMENT (FILE_TRACKING_ARCHITECTURE_DECISION.md):
    - Uses IAsyncBlobRepository for content storage
    - Uses IAsyncFileCommitRepository for commit management  
    - Uses IAsyncCheckpointFileLinkRepository for checkpoint links
    - All operations through UoW for ACID compliance
    """
    
    def __init__(
        self,
        uow_factory: Callable[[], IAsyncUnitOfWork],
    ):
        self._uow_factory = uow_factory
    
    async def _path_exists(self, path: Path) -> bool:
        """
        Check if path exists asynchronously.
        """
        try:
            await aiofiles.os.stat(path)
            return True
        except FileNotFoundError:
            return False
    
    async def atrack_files(
        self,
        file_paths: List[str],
        message: str,
        checkpoint_id: Optional[str] = None,
    ) -> FileTrackingResult:
        """
        Track files asynchronously with content-addressable storage.
        """
        async with self._uow_factory() as uow:
            mementos = []
            total_size = 0
            
            for file_path in file_paths:
                path = Path(file_path)
                if not await self._path_exists(path):
                    continue
                
                # Read file content asynchronously
                async with aiofiles.open(path, 'rb') as f:
                    content = await f.read()
                
                # Save via repository (content-addressable)
                blob_id = await uow.blobs.asave(content)
                
                mementos.append(FileMemento(
                    file_path=str(path),
                    file_hash=blob_id,
                    file_size=len(content),
                ))
                total_size += len(content)
            
            # Create commit and add mementos
            commit = FileCommit.create(message=message)
            for memento in mementos:
                commit.add_memento(memento)
            await uow.file_commits.asave(commit)
            
            # Link to checkpoint if provided
            if checkpoint_id:
                # Convert checkpoint_id to int if possible
                try:
                    cp_id_val = int(checkpoint_id)
                except ValueError:
                    # If not convertible to int, skip linking and log warning
                    logger.warning(f"checkpoint_id '{checkpoint_id}' is not an integer, skipping link")
                    cp_id_val = None
                
                if cp_id_val is not None:
                    link = CheckpointFileLink.create_from_values(
                        checkpoint_id=cp_id_val,
                        commit_id=commit.commit_id,
                        file_count=len(mementos),
                        total_size_bytes=total_size,
                    )
                    await uow.checkpoint_file_links.aadd(link)
            
            await uow.acommit()  # ATOMIC: blobs + commit + link
            
            return FileTrackingResult(
                commit_id=commit.commit_id.value,
                files_tracked=len(mementos),
                total_size_bytes=total_size,
            )
    
    async def arestore_files(
        self,
        checkpoint_id: str,
        output_dir: Path,
    ) -> int:
        """
        Restore files from checkpoint asynchronously.
        """
        async with self._uow_factory() as uow:
            # Get commit via checkpoint link
            # Same checkpoint_id type issue.
            commit = await uow.file_commits.aget_by_checkpoint_id(checkpoint_id)
            if not commit:
                return 0
            
            restored_count = 0
            for memento in commit.mementos:
                # Restore via repository
                output_path = output_dir / Path(memento.file_path).name
                try:
                    await uow.blobs.arestore_to_file(
                        blob_id=memento.file_hash,
                        output_path=output_path,
                    )
                    restored_count += 1
                except FileNotFoundError:
                    # Blob may have been orphaned/cleaned - log and continue
                    logger.warning(f"Blob not found: {memento.file_hash}")
            
            return restored_count
    
    async def atrack_and_link(
        self,
        checkpoint_id: str,
        file_paths: List[str],
        message: str,
    ) -> FileTrackingResult:
        """
        Convenience method: Track files and link to checkpoint in one call.
        """
        return await self.atrack_files(
            file_paths=file_paths,
            message=message,
            checkpoint_id=checkpoint_id,
        )
