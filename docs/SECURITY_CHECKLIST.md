# Operator security checklist

Before production use:

- run YaCompress with the least privileges required;
- protect source, destination, and manifest directories from untrusted writers;
- install native archive tools from trusted operating-system repositories;
- keep Ansible, the Collection, and native tools updated;
- test Check Mode before changing retention policies;
- validate real NFS, clustered storage, SELinux, AppArmor, and FIPS environments on the target host;
- ensure enough temporary space exists beside each destination archive;
- quiesce applications or use consistent snapshots before archiving mutable data;
- store manifests separately or protect them from modification together with archives;
- perform periodic structural checks, manifest verification, and actual restore tests;
- treat external archives as hostile and extract them only in isolated, unprivileged directories;
- use encrypted transport and storage when backup confidentiality is required;
- bound compression threads and monitor CPU, memory, inodes, quotas, and backup windows.

See [`../SECURITY.md`](../SECURITY.md) for the complete threat model and reporting policy.
