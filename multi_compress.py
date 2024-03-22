#!/usr/bin/python

# Copyright (c) 2024 Aleksej Voronin
# MIT License

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: multi_archive

short_description: Archives or unarchives files and directories with optional compression.

version_added: "1.1.5"

description:
    - This module provides functionality for archiving and unarchiving files and directories.
    - Supports tar.gz, tar.bz2, and zip formats.
    - Allows for the use of pigz for parallel gzip compression and decompression, providing performance benefits on multicore systems.
    - Offers options to include or exclude specific files or patterns.
    - Can automatically detect the archive format for unarchiving operations.

options:
    source:
        description: The source file or directory to archive or unarchive.
        required: true
        type: str
    dest:
        description: The destination file or directory for the archive or unarchive operation.
        required: true
        type: str
    format:
        description: The archive format (tar.gz, tar.bz2, zip). For unarchiving, this is optional and will be auto-detected.
        required: false
        type: str
        choices: ['tar.gz', 'tar.bz2', 'zip']
    compression:
        description: The compression method (none, gzip, pigz). Defaults to none, which uses the default method based on the format.
        required: false
        type: str
        choices: ['none', 'gzip', 'pigz']
    state:
        description: Whether to archive (archived) or unarchive (unarchived) the source.
        required: true
        type: str
        choices: ['archived', 'unarchived']
    delete_source:
        description: Whether to delete the source file or directory after archiving or unarchiving.
        required: false
        default: false
        type: bool
    include:
        description: List of files or patterns to include in the archive. Only valid for archiving.
        required: false
        type: list
        elements: str
    exclude:
        description: List of files or patterns to exclude from the archive. Only valid for archiving.
        required: false
        type: list
        elements: str

author:
    - Aleksej Voronin (@mrAibo)
'''

EXAMPLES = r'''
# Archive a directory with tar.gz using pigz
- name: Archive directory
  community.general.multi_archive:
    source: /path/to/directory
    dest: /path/to/archive.tar.gz
    format: tar.gz
    compression: pigz
    state: archived
    delete_source: false

# Unarchive a tar.gz file with automatic format detection
- name: Unarchive tar.gz
  community.general.multi_archive:
    source: /path/to/archive.tar.gz
    dest: /path/to/directory
    state: unarchived
    delete_source: false

# Archive a directory with tar.gz, excluding certain patterns
- name: Archive a directory with tar.gz, excluding certain patterns
  community.general.multi_archive:
    name: /path/to/source
    dest: /path/to/destination/exclude_specific.tar.gz
    format: tar.gz
    exclude:
      - "*.log"
      - "*.tmp"
    state: archived

#  Archive specific files within a directory into tar.gz
- name: Archive specific files within a directory into tar.gz
  community.general.multi_archive:
    source: /path/to/source
    dest: /path/to/destination/include_specific.tar.gz
    format: tar.gz
    include:
      - "important.txt"
      - "docs/"
    state: archived
     
'''

RETURN = r'''
original_source:
    description: The original source file or directory that was specified.
    type: str
    returned: always
    sample: '/path/to/directory'
destination:
    description: The destination file or directory specified for the operation.
    type: str
    returned: always
    sample: '/path/to/archive.tar.gz'
compression_used:
    description: The compression method that was used for the operation.
    type: str
    returned: when relevant
    sample: 'pigz'
format_detected:
    description: The archive format that was detected for unarchiving.
    type: str
    returned: on unarchive if format was auto-detected
    sample: 'tar.gz'
'''


# Import required libraries
import os
import subprocess
import shutil
from ansible.module_utils.basic import AnsibleModule

def run_command(command):
    """Run shell command and return the output"""
    try:
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
        return (True, output.strip())
    except subprocess.CalledProcessError as e:
        return (False, e.output.strip())

def archive(module, **kwargs):
    # Access to the arguments via kwargs
    source = kwargs.get('source')
    dest = kwargs.get('dest')
    format = kwargs.get('format')
    delete_source = kwargs.get('delete_source', False)  # Default value is False if not specified
    compression = kwargs.get('compression', 'none')  # Default value is 'none' if not specified
    include = kwargs.get('include', [])
    exclude = kwargs.get('exclude', [])
    
#    module.log(msg=f"delete_source is set to {delete_source}")    
    """Extend the archiving function with optional compression."""
    cmd = "tar"
    
    if format in ["tar.gz", "tar.bz2"]:
        if format == "tar.gz":
            cmd += " -z" if compression == "none" else " -I pigz"
        elif format == "tar.bz2":
            cmd += " -j"
        
        cmd += f" -cf {dest}"
        
        if exclude:
            for pattern in exclude:
                cmd += f" --exclude='{pattern}'"
        if include:
            cmd += " " + " ".join(include)
        else:
            cmd += f" {source}"
    elif format == "zip":
        # ZIP format logic remains unchanged
        cmd = f"zip -r {dest} {source}"
    else:
        module.fail_json(msg=f"Unsupported format: {format}")

    success, output = run_command(cmd)
    if not success:
        module.fail_json(msg=f"Failed to archive {source}: {output}")
    
#    module.warn(f"delete_source is set to {delete_source}")
    if delete_source:
        if os.path.isdir(source):
            shutil.rmtree(source)
        else:
            os.remove(source)

    module.exit_json(changed=True, msg=f"{source} archived to {dest} successfully.")

def ensure_directory_exists(path):
    """Ensure that the destination directory exists."""
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)

def detect_archive_format(source):
    """Detect the archive format based on the file extension."""
    if source.endswith('.zip'):
        return 'zip'
    elif source.endswith('.tar.gz') or source.endswith('.tgz'):
        return 'tar.gz'
    elif source.endswith('.tar.bz2') or source.endswith('.tbz'):
        return 'tar.bz2'
    else:
        # If no supported format was recognised, return None or an error
        return None

def unarchive(module, **kwargs):
    source = kwargs.get('source')
    dest = kwargs.get('dest')
    format = kwargs.get('format', None)
    delete_source = kwargs.get('delete_source', False)
    
    # Ensure that the target directory exists
    ensure_directory_exists(dest)

    # Automatically recognise format if not specified
    if not format:
        format = detect_archive_format(source)
    
    cmd = None  # Initialisation of cmd with None
    
    if format == 'zip':
        cmd = f"unzip -o '{source}' -d '{dest}'"
    elif format == 'tar.gz':
        cmd = f"tar -xzf '{source}' -C '{dest}'"
    elif format == 'tar.bz2':
        cmd = f"tar -xjf '{source}' -C '{dest}'"
    else:
        module.fail_json(msg=f"Unsupported archive format: {format}")

    if cmd:  # Check whether cmd has a value before it is used
        # Log the executed command
        module.log(msg=f"Executing command: {cmd}")
        success, output = run_command(cmd)
        if not success:
            module.fail_json(msg=f"Failed to unarchive {source}: {output}")
    
        # Delete the source archive, if requested
        if delete_source:
            os.remove(source)
    
        module.exit_json(changed=True, msg=f"{source} successfully unarchived to {dest}.")
    else:
        module.fail_json(msg="No command was set for unarchiving, this should not happen.")



def detect_format(name, default_format='tar.gz'):
    """Detect the archive format from the file extension"""
    if name.endswith('.tar.gz') or name.endswith('.tgz'):
        return 'tar.gz'
    elif name.endswith('.zip'):
        return 'zip'
    elif name.endswith('.tar'):
        return 'tar'
    else:
        return default_format

def main():
    module_args = {
        'source': {'type': 'str', 'required': True},
        'dest': {'type': 'str', 'required': True},
        'format': {'type': 'str', 'required': False, 'default': None, 'choices': ['tar.gz', 'tar.bz2', 'zip']},
        # Change: Set 'default' for 'format' to None
        'compression': {'type': 'str', 'required': False, 'default': 'none', 'choices': ['gzip', 'pigz', 'none']},
        'state': {'type': 'str', 'required': True, 'choices': ['archived', 'unarchived']},
        'delete_source': {'type': 'bool', 'required': False, 'default': False},
        'include': {'type': 'list', 'elements': 'str', 'default': []},
        'exclude': {'type': 'list', 'elements': 'str', 'default': []},
    }

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    # Determine format based on file extension, if not explicitly specified
    if not module.params['format']:
        module.params['format'] = detect_archive_format(module.params['source'])

    if module.params['state'] == 'archived':
        archive(module, **module.params)
    else:
        unarchive(module, **module.params)

if __name__ == '__main__':
    main()
