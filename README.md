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

- `name`: Path to the file or directory to archive or unarchive.
- `dest`: Destination path for the archive file or unarchiving operation.
- `format`: (Optional) Specifies the archive format (`tar.gz`, `tar.bz2`, `zip`). Automatically detected during unarchiving if not provided.
- `compression`: (Optional) Compression method to use (`gzip`, `pigz`, `none`). Defaults to `none`, which uses the default compression method for the specified format.
- `state`: Determines the operation (`archived` or `unarchived`).
- `delete_source`: (Optional) Whether to delete the source files/directories after operation. Defaults to `False`.
- `include`: (Optional) List of files or patterns to include in the archive.
- `exclude`: (Optional) List of files or patterns to exclude from the archive.

### Example Playbook

```yaml
- hosts: localhost
  tasks:
    - name: Archive a directory with tar.gz using pigz
      community.general.multi_archive:
        name: /path/to/source
        dest: /path/to/destination/archive.tar.gz
        format: tar.gz
        compression: pigz
        state: archived
        delete_source: false

    - name: Unarchive the tar.gz file
      community.general.multi_archive:
        name: /path/to/destination/archive.tar.gz
        dest: /path/to/unarchive/destination
        state: unarchived
```

This module aims to be a go-to solution for managing archives in Ansible playbooks, offering both power and simplicity for handling various file archiving tasks.

---

Feel free to contribute to the module by submitting issues and pull requests on GitHub. Your feedback and contributions are welcome to help make the Multi Archive module even better for the Ansible community.
