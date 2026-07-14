# Development rules

Apply the Ponytail ladder before changing code:

1. Confirm the change is needed.
2. Reuse existing code and Ansible functionality.
3. Prefer Python's standard library and native archive tools.
4. Add no dependency unless the existing platform cannot solve the problem cleanly.
5. Make the smallest understandable change in the correct place.

Project-specific constraints:

- Keep the module focused on archive operations, especially parallel gzip through `pigz`.
- Prefer `ansible.builtin.unarchive` for playbooks that only need extraction.
- Do not report `changed: false` when a command rewrote files.
- Check mode must not modify the filesystem.
- Destructive source deletion requires successful completion and archive verification.
- Reject unsafe source, destination, and include path relationships.
- Non-trivial behavior needs a runnable test in `tests.yml`.
