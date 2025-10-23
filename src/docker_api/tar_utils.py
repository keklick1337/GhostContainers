"""
TAR Archive utilities for Docker file operations
"""

import tarfile
import io
import os
from typing import Optional


def create_tar_from_file(file_path: str, arcname: Optional[str] = None) -> bytes:
    """
    Create tar archive from a single file
    
    Args:
        file_path: Path to file to archive
        arcname: Name of file in archive (default: basename of file_path)
        
    Returns:
        Tar archive as bytes
    """
    if arcname is None:
        arcname = os.path.basename(file_path)
    
    tar_stream = io.BytesIO()
    
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        tar.add(file_path, arcname=arcname)
    
    tar_stream.seek(0)
    return tar_stream.read()


def create_tar_from_directory(dir_path: str, arcname: Optional[str] = None) -> bytes:
    """
    Create tar archive from a directory
    
    Args:
        dir_path: Path to directory to archive
        arcname: Name of directory in archive (default: basename of dir_path)
        
    Returns:
        Tar archive as bytes
    """
    if arcname is None:
        arcname = os.path.basename(dir_path)
    
    tar_stream = io.BytesIO()
    
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        tar.add(dir_path, arcname=arcname)
    
    tar_stream.seek(0)
    return tar_stream.read()


def extract_tar_to_file(tar_data: bytes, output_path: str, filename: Optional[str] = None):
    """
    Extract file from tar archive
    
    Args:
        tar_data: Tar archive as bytes
        output_path: Directory where to extract
        filename: Specific file to extract (default: extract all)
    """
    tar_stream = io.BytesIO(tar_data)
    
    with tarfile.open(fileobj=tar_stream, mode='r') as tar:
        if filename:
            # Extract specific file
            member = tar.getmember(filename)
            tar.extract(member, path=output_path)
        else:
            # Extract all
            tar.extractall(path=output_path)


def list_tar_contents(tar_data: bytes) -> list:
    """
    List contents of tar archive
    
    Args:
        tar_data: Tar archive as bytes
        
    Returns:
        List of filenames in archive
    """
    tar_stream = io.BytesIO(tar_data)
    
    with tarfile.open(fileobj=tar_stream, mode='r') as tar:
        return tar.getnames()
