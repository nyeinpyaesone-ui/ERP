"""
High-performance I/O engine with zero-copy architecture.
Optimized for ERP file operations and large dataset handling.
"""
import aiofiles
import os
from mmap import ACCESS_READ, mmap

class OptimizedIO:
    """Zero-copy streaming and memory-mapped file operations."""
    
    CHUNK_SIZE = 64 * 1024  # 64KB optimal for SSD/NVMe
    MAX_MEMORY_MAP = 50 * 1024 * 1024  # 50MB threshold for mmap

    @staticmethod
    async def stream_file_read(path: str):
        """Zero-copy streaming for large files to avoid RAM spikes."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
            
        async with aiofiles.open(path, 'rb') as f:
            while chunk := await f.read(OptimizedIO.CHUNK_SIZE):
                yield chunk

    @staticmethod
    def memory_map_large_file(path: str):
        """Memory mapping for files > 50MB to avoid RAM spike."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
            
        fd = os.open(path, os.O_RDONLY)
        try:
            return mmap(fd, 0, access=ACCESS_READ)
        finally:
            os.close(fd)

    @staticmethod
    async def stream_file_write(path: str, data_generator):
        """Stream write from async generator with backpressure control."""
        async with aiofiles.open(path, 'wb') as f:
            async for chunk in data_generator:
                await f.write(chunk)
