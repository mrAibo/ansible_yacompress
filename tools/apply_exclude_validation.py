#!/usr/bin/env python3
from pathlib import Path

MODULES = [Path('multi_archive.py'), Path('plugins/modules/multi_archive.py')]

OLD_DOC = """  exclude:\n    description: Archive path patterns to exclude while archiving.\n    type: list\n"""
NEW_DOC = """  exclude:\n    description:\n      - Relative archive path patterns to exclude while archiving.\n      - Absolute paths and patterns that escape through C(..) are rejected.\n    type: list\n"""
MARKER = "def _expand_includes(module, source, include):\n"
HELPER = """def _validate_patterns(module, name, patterns):\n    for pattern in patterns:\n        if os.path.isabs(pattern):\n            module.fail_json(msg=\"%s entries must be relative: %s\" % (name, pattern))\n        normalized = os.path.normpath(pattern)\n        if normalized == os.pardir or normalized.startswith(os.pardir + os.sep):\n            module.fail_json(msg=\"%s entry escapes source: %s\" % (name, pattern))\n\n\n"""
OLD_VALIDATE_END = """    if include and not os.path.isdir(sources[0]):\n        module.fail_json(msg=\"include requires source to be a directory\")\n    return sources\n"""
NEW_VALIDATE_END = """    if include and not os.path.isdir(sources[0]):\n        module.fail_json(msg=\"include requires source to be a directory\")\n    _validate_patterns(module, 'exclude', exclude)\n    return sources\n"""

for path in MODULES:
    text = path.read_text(encoding='utf-8')
    text = text.replace(OLD_DOC, NEW_DOC, 1)
    if HELPER not in text:
        text = text.replace(MARKER, HELPER + MARKER, 1)
    text = text.replace(OLD_VALIDATE_END, NEW_VALIDATE_END, 1)
    path.write_text(text, encoding='utf-8')

unit = Path('tests/test_multi_archive.py')
text = unit.read_text(encoding='utf-8')
marker = "    def test_tar_rewrite_include_and_metrics(self):\n"
test = """    def test_exclude_patterns_reject_absolute_and_parent_traversal(self):\n        multi_archive._validate_patterns(\n            self.module, 'exclude', ['*.log', 'cache/**', 'dir/../dir/*.tmp']\n        )\n        for pattern in ['/etc/passwd', '../secret', 'cache/../../secret']:\n            with self.subTest(pattern=pattern):\n                with self.assertRaises(FailResult):\n                    multi_archive._validate_patterns(self.module, 'exclude', [pattern])\n\n"""
if test not in text:
    text = text.replace(marker, test + marker, 1)
unit.write_text(text, encoding='utf-8')

integration = Path('tests/integration/targets/multi_archive/tasks/main.yml')
text = integration.read_text(encoding='utf-8')
marker = "    - name: Predict archive creation in check mode\n"
tasks = """    - name: Reject parent-traversal exclude pattern\n      mraibo.yacompress.multi_archive:\n        source: \"{{ workspace.path }}/config\"\n        dest: \"{{ workspace.path }}/unsafe-exclude.tar.gz\"\n        state: archived\n        exclude:\n          - ../outside\n      register: unsafe_exclude\n      ignore_errors: true\n\n    - name: Validate unsafe exclude rejection\n      ansible.builtin.assert:\n        that:\n          - unsafe_exclude is failed\n          - \"'exclude entry escapes source' in unsafe_exclude.msg\"\n\n"""
if tasks not in text:
    text = text.replace(marker, tasks + marker, 1)
integration.write_text(text, encoding='utf-8')
