# Multi Archive Ansible Module

The Multi Archive module is a versatile Ansible module designed to facilitate the archiving and unarchiving of files and directories with support for multiple formats and compression methods. It extends Ansible's capabilities to manage archives more efficiently, offering flexibility and performance for various use cases. The module integrates seamlessly with Ansible's automation workflows, making it easier to manage file archives in your infrastructure.

## Features

- **Support for Multiple Archive Formats**: Handles common archive formats including `tar.gz`, `tar.bz2`, and `zip`, covering a wide range of archiving needs.
- **Compression and Decompression**: Offers compression using `gzip`, `bzip2`, and the parallel compression utility `pigz` for faster compression speeds on multicore systems. Decompression is automatically handled based on the archive format.
- **Flexible File Inclusion/Exclusion**: Allows specifying files or patterns to include or exclude from the archive, providing control over the archive's contents.
- **Automatic Format Detection**: For unarchiving tasks, the module can automatically detect the archive format based on the file extension, simplifying task definitions.
- **Optional Source Deletion**: After successful archiving or unarchiving, the source files or directories can be optionally deleted, helping manage disk space.

## Usage

### Parameters

- `source`: Path to the file or directory to archive or unarchive.
- `dest`: Destination path for the archive file or unarchiving operation.
- `format`: (Optional) Specifies the archive format (`tar.gz`, `tar.bz2`, `zip`). Automatically detected during unarchiving if not provided.
- `compression`: (Optional) Compression method to use (`gzip`, `pigz`, `none`). Defaults to `none`, which uses the default compression method for the specified format.
- `state`: Determines the operation (`archived` or `unarchived`).
- `delete_source`: (Optional) Whether to delete the source files/directories after operation. Defaults to `False`.
- `include`: (Optional) List of files or patterns to include in the archive.
- `exclude`: (Optional) List of files or patterns to exclude from the archive.

### Example 1: Compressing a Directory with `pigz`

This example shows how to compress a directory into a `tar.gz` archive using `pigz` for faster compression. This is particularly useful for large directories where compression speed is a concern.

```yaml
- hosts: localhost
  tasks:
    - name: Compress a directory into tar.gz using pigz
      community.general.multi_archive:
        source: /path/to/large/directory
        dest: /path/to/destination/large_directory_compressed.tar.gz
        format: tar.gz
        compression: pigz
        state: archived
        delete_source: false
```

### Example 2: Decompressing a `tar.gz` Archive with Automatic Detection

Although `pigz` is primarily used for compression, this example focuses on the automatic detection feature of the module during decompression. The module can automatically detect `tar.gz` format and use the appropriate method for decompression.

```yaml
- hosts: localhost
  tasks:
    - name: Decompress a tar.gz archive with automatic format detection
      community.general.multi_archive:
        source: /path/to/destination/large_directory_compressed.tar.gz
        dest: /path/to/unarchive/destination
        state: unarchived
        delete_source: false
```

### Handling with the Module

The Multi Archive module is designed to handle the inclusion of `pigz` for compression seamlessly. Here's how it integrates with the module and what users should know:

- **Parameter Specification**: To use `pigz` for compression, simply specify `compression: pigz` in your task. The module takes care of the rest, invoking `pigz` for parallel compression of `tar.gz` archives.
- **Speed Benefits**: Using `pigz` can significantly reduce compression times for large datasets by leveraging multiple CPU cores.
- **Fallback**: If `pigz` is not available on the system, it's a good practice to ensure that your playbook can gracefully fall back to using standard `gzip` compression. This can be managed via error handling in Ansible or by having a conditional logic based on the availability of `pigz` on the target system.

### Example 3: Conditional Use of `pigz`

This example demonstrates how you might conditionally use `pigz` if it's available, falling back to `gzip` otherwise. This requires a bit more setup, including a task to check for `pigz` availability.

```yaml
- hosts: localhost
  tasks:
    - name: Check for pigz availability
      command: which pigz
      register: pigz_installed
      ignore_errors: true

    - name: Compress a directory using pigz if available, else gzip
      community.general.multi_archive:
        source: /path/to/directory
        dest: /path/to/destination/directory_compressed.tar.gz
        format: tar.gz
        compression: "{{ 'pigz' if pigz_installed.rc == 0 else 'gzip' }}"
        state: archived
        delete_source: false
```

By incorporating these practices and examples, users can effectively utilize the Multi Archive module in their Ansible playbooks, taking advantage of `pigz` for improved compression performance where applicable.


This module aims to be a go-to solution for managing archives in Ansible playbooks, offering both power and simplicity for handling various file archiving tasks.

---

Feel free to contribute to the module by submitting issues and pull requests on GitHub. Your feedback and contributions are welcome to help make the Multi Archive module even better for the Ansible community.
