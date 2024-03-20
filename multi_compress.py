#!/usr/bin/python
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
    # Zugriff auf die Argumente über kwargs
    source = kwargs.get('source')
    dest = kwargs.get('dest')
    format = kwargs.get('format')
    delete_source = kwargs.get('delete_source', False)  # Standardwert ist False, wenn nicht angegeben
    compression = kwargs.get('compression', 'none')  # Standardwert ist 'none', wenn nicht angegeben
    include = kwargs.get('include', [])
    exclude = kwargs.get('exclude', [])
    
#    module.log(msg=f"delete_source is set to {delete_source}")    
    """Erweitern der Archivierungsfunktion um optionale Kompression."""
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
        # ZIP-Format Logik bleibt unverändert
        cmd = f"zip -r {dest} {source}"
    else:
        module.fail_json(msg=f"Unsupported format: {format}")

    success, output = run_command(cmd)
    if not success:
        module.fail_json(msg=f"Failed to archive {source}: {output}")
    
    module.warn(f"delete_source is set to {delete_source}")
    if delete_source:
        if os.path.isdir(source):
            shutil.rmtree(source)
        else:
            os.remove(source)

    module.exit_json(changed=True, msg=f"{name} archived to {dest} successfully.")

def ensure_directory_exists(path):
    """Ensure that the destination directory exists."""
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)

def detect_archive_format(name):
    """Detect the archive format based on the file extension."""
    if name.endswith('.tar.gz') or name.endswith('.tgz'):
        return 'tar.gz'
    elif name.endswith('.tar.bz2') or name.endswith('.tbz2'):
        return 'tar.bz2'
    elif name.endswith('.zip'):
        return 'zip'
    else:
        return None


def unarchive(module, **kwargs):
    # Zugriff auf die Argumente über kwargs
    source = kwargs.get('source')
    dest = kwargs.get('dest')
    format = kwargs.get('format', None)  # Standardwert ist None, wenn nicht angegeben
    delete_source = kwargs.get('delete_source', False)  # Standardwert ist False, wenn nicht angegeben
    compression = kwargs.get('compression', 'none')  # Standardwert ist 'none', wenn nicht angegeben
    
    # Stellen Sie sicher, dass das Zielverzeichnis existiert
    ensure_directory_exists(dest)

    # Format automatisch erkennen, wenn es nicht angegeben wurde
    if not format:
        format = detect_archive_format(source)
        if not format:
            module.fail_json(msg="Could not detect archive format. Please specify the format.")
    
    # Konstruktion des Dearchivierungsbefehls basierend auf dem Format
    cmd = "tar"
    if format == 'tar.gz':
        cmd += " -I pigz" if compression == "pigz" else " -z"
    elif format == 'tar.bz2':
        cmd += " -j"
    elif format == 'zip':
        cmd = f"unzip {source} -d {dest}"
    else:
        module.fail_json(msg=f"Unsupported archive format: {format}")
    
    cmd += f" -xf {source} -C {dest}"

    # Dearchivierungsbefehl ausführen
    success, output = run_command(cmd)
    if not success:
        module.fail_json(msg=f"Failed to unarchive {source}: {output}")
    
    # Quellarchiv löschen, falls angefordert
    if delete_source:
        os.remove(source)
    
    module.exit_json(changed=True, msg=f"{name} successfully unarchived to {dest}.")

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
        'format': {'type': 'str', 'required': False, 'default': 'tar.gz', 'choices': ['tar.gz', 'tar.bz2', 'zip']},
        'compression': {'type': 'str', 'required': False, 'default': 'none', 'choices': ['gzip', 'pigz', 'none']},
        'state': {'type': 'str', 'required': True, 'choices': ['archived', 'unarchived']},
        'delete_source': {'type': 'bool', 'required': False, 'default': False},
        'include': {'type': 'list', 'elements': 'str', 'default': []},
        'exclude': {'type': 'list', 'elements': 'str', 'default': []},
    }

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    if module.params['state'] == 'archived':
        archive(module, **module.params)
    else:
        unarchive(module, **module.params)

if __name__ == '__main__':
    main()

'''
Beispiel:
---
- name: Test the multi_archive module with include and exclude options
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Archive a directory with tar.gz using pigz, with specific includes and excludes
      community.general.multi_archive:
        source: /path/to/source/directory
        dest: /path/to/destination/example_archive.tar.gz
        format: tar.gz
        compression: pigz
        state: archived
        delete_source: false
        include:
          - "*.txt"  # Include all txt files
          - "important/"  # Include all files in the 'important' subdirectory
        exclude:
          - "*.log"  # Exclude all log files
          - "temp/"  # Exclude the 'temp' subdirectory

          
---
- name: Demonstrate the multi_archive module functionalities
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Archive a directory into tar.gz using default tar compression
      community.general.multi_archive:
        source: /path/to/source
        dest: /path/to/destination/default_compressed.tar.gz
        format: tar.gz
        state: archived

    - name: Archive a directory into tar.bz2 using default bzip2 compression
      community.general.multi_archive:
        source: /path/to/source
        dest: /path/to/destination/default_compressed.tar.bz2
        format: tar.bz2
        state: archived

    - name: Archive a directory with tar.gz, excluding certain patterns
      community.general.multi_archive:
        name: /path/to/source
        dest: /path/to/destination/exclude_specific.tar.gz
        format: tar.gz
        exclude:
          - "*.log"
          - "*.tmp"
        state: archived

    - name: Archive specific files within a directory into tar.gz
      community.general.multi_archive:
        source: /path/to/source
        dest: /path/to/destination/include_specific.tar.gz
        format: tar.gz
        include:
          - "important.txt"
          - "docs/"
        state: archived

    - name: Unarchive a tar.gz file using default gzip decompression
      community.general.multi_archive:
        source: /path/to/destination/default_compressed.tar.gz
        dest: /path/to/unarchive/destination
        state: unarchived

---
- name: Demonstrate the multi_archive module with pigz compression
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Archive a directory into tar.gz using pigz for faster compression
      community.general.multi_archive:
        source: /path/to/source/directory
        dest: /path/to/destination/pigz_compressed.tar.gz
        format: tar.gz
        compression: pigz
        state: archived

    - name: Unarchive a tar.gz file using pigz for faster decompression
      community.general.multi_archive:
        name: /path/to/destination/pigz_compressed.tar.gz
        dest: /path/to/unarchive/destination_pigz
        format: tar.gz
        compression: pigz
        state: unarchived

    - name: Archive a directory into tar.gz with pigz, excluding logs
      community.general.multi_archive:
        source: /path/to/another/source
        dest: /path/to/destination/pigz_exclude_logs.tar.gz
        format: tar.gz
        compression: pigz
        exclude:
          - "*.log"
        state: archived

    - name: Archive specific files within a directory into tar.gz using pigz
      community.general.multi_archive:
        source: /yet/another/path/to/source
        dest: /path/to/destination/pigz_include_specific.tar.gz
        format: tar.gz
        compression: pigz
        include:
          - "important_data.txt"
          - "critical_docs/"
        state: archived

'''
