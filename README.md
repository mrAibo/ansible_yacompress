# Multi Archive Ansible Module (`multi_archive.py`)

The Multi Archive module (`multi_archive.py`) is a versatile Ansible module designed to facilitate the archiving and unarchiving of files and directories with support for multiple formats and compression methods. It extends Ansible's capabilities to manage archives more efficiently, offering flexibility and performance for various use cases. The module integrates seamlessly with Ansible's automation workflows, making it easier to manage file archives in your infrastructure.

## Features

- **Support for Multiple Archive Formats**: Handles common archive formats including `tar.gz`, `tar.bz2`, and `zip`.
- **Flexible Compression**: Offers compression using `gzip`, `bzip2` (native to `tar`), and the parallel compression utility `pigz` for faster `tar.gz` compression on multicore systems. Decompression is automatically handled based on the archive format.
- **Flexible File Inclusion/Exclusion**: Allows specifying files or patterns to include or exclude from the archive (primarily for `tar` based formats), providing control over the archive's contents.
- **Automatic Format Detection**: For unarchiving tasks, the module can automatically detect the archive format based on the file extension, simplifying task definitions.
- **Optional Source Deletion**: After successful archiving or unarchiving, the source files or directories can be optionally deleted.

## Parameters

- `source`: Path to the file or directory to archive or unarchive. (Required)
- `dest`: Destination path for the archive file or unarchiving operation. (Required)
- `format`: (Optional) Specifies the archive format (`tar.gz`, `tar.bz2`, `zip`). Automatically detected during unarchiving if not provided based on the source file extension.
- `compression`: (Optional for `tar.gz`) Compression method to use (`gzip`, `pigz`, `none`). Defaults to `none`, which uses the default compression for the specified format (e.g., `gzip` for `tar.gz`). For `tar.bz2` and `zip`, compression is inherent to the format.
- `state`: Determines the operation (`archived` or `unarchived`). (Required)
- `delete_source`: (Optional) Whether to delete the source files/directories after operation. Defaults to `False`.
- `include`: (Optional) List of files or patterns to include in the archive. Primarily for `tar`-based formats.
- `exclude`: (Optional) List of files or patterns to exclude from the archive. Primarily for `tar`-based formats and `zip`.

## Usage

**Note on Module Invocation:**
The examples below use `multi_archive` as the module name. If you are using this module as part of a custom collection (e.g., `your_namespace.your_collection.multi_archive`), you would call it by its Fully Qualified Collection Name (FQCN). If the module script `multi_archive.py` is placed in a local `library` directory adjacent to your playbook, Ansible will automatically find it with the name `multi_archive`.

### Example 1: Compressing a Directory with `pigz`

This example shows how to compress a directory into a `tar.gz` archive using `pigz` for faster compression.

```yaml
- hosts: localhost
  tasks:
    - name: Compress a directory into tar.gz using pigz
      multi_archive:
        source: /path/to/large/directory
        dest: /path/to/destination/large_directory_compressed.tar.gz
        format: tar.gz
        compression: pigz
        state: archived
        delete_source: false
```

### Example 2: Decompressing a `tar.gz` Archive with Automatic Detection

The module can automatically detect `tar.gz` format for decompression.

```yaml
- hosts: localhost
  tasks:
    - name: Decompress a tar.gz archive with automatic format detection
      multi_archive:
        source: /path/to/destination/large_directory_compressed.tar.gz
        dest: /path/to/unarchive/destination
        state: unarchived
        delete_source: false
```

### Example 3: Archiving with Include and Exclude (tar.gz)

This example demonstrates using `include` and `exclude` parameters.

```yaml
- hosts: localhost
  tasks:
    - name: Archive specific content from a directory
      multi_archive:
        source: /path/to/source_files # Directory containing files
        dest: /path/to/destination/custom_archive.tar.gz
        format: tar.gz
        state: archived
        include:
          - "important_docs/"
          - "*.txt"
        exclude:
          - "temp_files/"
          - "*.log"
```

### Example 4: Conditional Use of `pigz`

This example demonstrates how you might conditionally use `pigz` if it's available, falling back to `gzip` (by specifying `compression: none` or `compression: gzip` for `tar.gz`).

```yaml
- hosts: localhost
  tasks:
    - name: Check for pigz availability
      ansible.builtin.command: which pigz
      register: pigz_check
      ignore_errors: true
      changed_when: false

    - name: Compress a directory using pigz if available, else gzip
      multi_archive:
        source: /path/to/directory
        dest: /path/to/destination/directory_compressed.tar.gz
        format: tar.gz
        compression: "{{ 'pigz' if pigz_check.rc == 0 else 'gzip' }}" # 'gzip' or 'none'
        state: archived
```

## Testing

The module includes a test suite in `tests.yml`. This Ansible playbook contains various test cases to verify the functionality of `multi_archive.py`, including different archive formats, compression methods, include/exclude options, source deletion, and automatic format detection. To run the tests, ensure Ansible is installed and execute `ansible-playbook tests.yml` from the repository root (you might need to set `ANSIBLE_LIBRARY=.` if the module is not in a standard library path).

## Future Enhancements and Considerations

While `multi_archive.py` is functional, the following areas could be considered for future enhancements:

- **Built-in `pigz` Fallback**: The module could internally check for `pigz` availability and automatically fall back to `gzip` if `pigz` is specified but not found, simplifying playbook logic.
- **Idempotency**: True idempotency for Ansible modules ensures that if a task is run multiple times, it only performs actions if the desired state hasn't been reached. For this module, it would mean:
    - **Archiving**: If the destination archive exists and its contents perfectly match the source files, the module should report `changed=False`. Currently, it might recreate the archive and report `changed=True`.
    - **Unarchiving**: If the destination directory exists and its contents match the archive, it should report `changed=False`. Currently, it typically overwrites and reports `changed=True`.
    Implementing full idempotency can be complex, involving checksum comparisons or dry-run creations.
- **Expanded Format Support**: Add support for other archive formats like `tar.xz` or `7z`.
- **Password Protection**: Introduce options for creating encrypted/password-protected archives for supported formats (e.g., `zip`).
- **Checksum Verification**: Option to verify archive integrity after creation or before extraction using checksums.
- **More Granular `include`/`exclude` for `zip`**: The current `zip` command construction in the module is basic. More advanced `include`/`exclude` for `zip` might require listing files explicitly or using `find` in conjunction with `zip`.

---

This module aims to be a go-to solution for managing archives in Ansible playbooks. Your feedback and contributions are welcome to help make the Multi Archive module even better for the Ansible community. Feel free to contribute by submitting issues and pull requests.
