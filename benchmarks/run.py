import argparse
import csv
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


CASES = (
    {
        'name': 'yacompress-pigz',
        'archive': 'result.tar.gz',
        'task': """mraibo.yacompress.multi_archive:
        source: {source}
        dest: {dest}
        state: archived
        compression: pigz
        compression_level: 3
        threads: auto
        verify_archive: true""",
    },
    {
        'name': 'yacompress-zstd',
        'archive': 'result.tar.zst',
        'task': """mraibo.yacompress.multi_archive:
        source: {source}
        dest: {dest}
        state: archived
        compression_level: 3
        threads: auto
        verify_archive: true""",
    },
    {
        'name': 'yacompress-xz',
        'archive': 'result.tar.xz',
        'task': """mraibo.yacompress.multi_archive:
        source: {source}
        dest: {dest}
        state: archived
        compression_level: 3
        threads: 2
        verify_archive: true""",
    },
    {
        'name': 'community-gzip',
        'archive': 'result.tar.gz',
        'community': True,
        'task': """community.general.archive:
        path: {source}
        dest: {dest}
        format: gz""",
    },
)


def parse_args():
    parser = argparse.ArgumentParser(description='Benchmark yacompress against community.general.archive.')
    parser.add_argument('--size-mib', type=int, default=64, help='Approximate large-file dataset size.')
    parser.add_argument('--small-files', type=int, default=2000, help='Number of small files in the metadata-heavy dataset.')
    parser.add_argument('--iterations', type=int, default=2, help='Measured iterations per case and dataset.')
    parser.add_argument('--output-dir', default='benchmark-results', help='Directory for CSV and Markdown results.')
    parser.add_argument('--skip-community', action='store_true', help='Skip community.general.archive cases.')
    return parser.parse_args()


def write_datasets(root, size_mib, small_files):
    datasets = {}

    large = root / 'large-compressible'
    large.mkdir()
    block = (b'yacompress benchmark data\n' * 4096)
    target = size_mib * 1024 * 1024
    with (large / 'payload.log').open('wb') as stream:
        written = 0
        while written < target:
            chunk = block[:min(len(block), target - written)]
            stream.write(chunk)
            written += len(chunk)
    datasets['large-compressible'] = large

    small = root / 'many-small-files'
    small.mkdir()
    for index in range(small_files):
        group = small / ('group-%03d' % (index % 50))
        group.mkdir(exist_ok=True)
        (group / ('file-%05d.txt' % index)).write_text(
            'file=%d\nvalue=%s\n' % (index, 'x' * 128),
            encoding='utf-8',
        )
    datasets['many-small-files'] = small

    mixed = root / 'mixed-data'
    mixed.mkdir()
    shutil.copy2(large / 'payload.log', mixed / 'application.log')
    compressed_source = mixed / 'already-compressed.bin.gz'
    subprocess.run(
        ['gzip', '-c', str(large / 'payload.log')],
        check=True,
        stdout=compressed_source.open('wb'),
    )
    for index in range(200):
        (mixed / ('config-%03d.ini' % index)).write_text(
            '[section]\nenabled=true\nindex=%d\n' % index,
            encoding='utf-8',
        )
    datasets['mixed-data'] = mixed

    return datasets


def directory_size(path):
    return sum(item.stat().st_size for item in path.rglob('*') if item.is_file())


def render_playbook(task, source, dest):
    task_body = task.format(source=json.dumps(str(source)), dest=json.dumps(str(dest)))
    indented = '\n'.join('      ' + line for line in task_body.splitlines())
    return """---
- name: Archive benchmark
  hosts: localhost
  gather_facts: false
  tasks:
    - name: Run archive case
%s
""" % indented


def run_case(case, dataset_name, source, work, iterations, env):
    rows = []
    source_bytes = directory_size(source)
    case_dir = work / dataset_name / case['name']
    case_dir.mkdir(parents=True, exist_ok=True)
    playbook = case_dir / 'benchmark.yml'
    archive = case_dir / case['archive']
    playbook.write_text(render_playbook(case['task'], source, archive), encoding='utf-8')

    for iteration in range(1, iterations + 1):
        archive.unlink(missing_ok=True)
        started = time.perf_counter()
        process = subprocess.run(
            ['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(playbook)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        elapsed = time.perf_counter() - started
        if process.returncode != 0:
            raise RuntimeError('%s failed:\n%s' % (case['name'], process.stdout))
        subprocess.run(['tar', '-tf', str(archive)], check=True, stdout=subprocess.DEVNULL)
        archive_bytes = archive.stat().st_size
        rows.append({
            'dataset': dataset_name,
            'case': case['name'],
            'iteration': iteration,
            'source_bytes': source_bytes,
            'archive_bytes': archive_bytes,
            'elapsed_seconds': round(elapsed, 6),
            'throughput_mib_s': round(source_bytes / 1048576.0 / elapsed, 3),
            'compression_ratio': round(archive_bytes / float(source_bytes), 6) if source_bytes else None,
        })
    return rows


def write_results(rows, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = (
        'dataset', 'case', 'iteration', 'source_bytes', 'archive_bytes',
        'elapsed_seconds', 'throughput_mib_s', 'compression_ratio',
    )
    with (output_dir / 'results.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    grouped = {}
    for row in rows:
        key = (row['dataset'], row['case'])
        grouped.setdefault(key, []).append(row)

    lines = [
        '# YaCompress benchmark results',
        '',
        '> Results depend on CPU, storage, cache state, data shape, and tool versions.',
        '',
        '| Dataset | Case | Avg seconds | Avg MiB/s | Avg ratio | Archive MiB |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for (dataset, case), values in sorted(grouped.items()):
        count = len(values)
        seconds = sum(item['elapsed_seconds'] for item in values) / count
        throughput = sum(item['throughput_mib_s'] for item in values) / count
        ratios = [item['compression_ratio'] for item in values if item['compression_ratio'] is not None]
        ratio = sum(ratios) / len(ratios) if ratios else 0
        archive_mib = sum(item['archive_bytes'] for item in values) / count / 1048576.0
        lines.append('| %s | %s | %.3f | %.1f | %.4f | %.2f |' % (
            dataset, case, seconds, throughput, ratio, archive_mib,
        ))
    (output_dir / 'results.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    args = parse_args()
    if args.size_mib < 1 or args.small_files < 1 or args.iterations < 1:
        raise SystemExit('size, small-files, and iterations must be positive')

    output_dir = Path(args.output_dir).resolve()
    env = os.environ.copy()
    env.setdefault('ANSIBLE_NOCOLOR', '1')

    with tempfile.TemporaryDirectory(prefix='yacompress-benchmark-') as temp:
        root = Path(temp)
        datasets = write_datasets(root / 'datasets', args.size_mib, args.small_files)
        work = root / 'work'
        cases = [case for case in CASES if not (args.skip_community and case.get('community'))]
        rows = []
        for dataset_name, source in datasets.items():
            for case in cases:
                print('Running %s on %s' % (case['name'], dataset_name), flush=True)
                rows.extend(run_case(case, dataset_name, source, work, args.iterations, env))
        write_results(rows, output_dir)

    print('Wrote %s and %s' % (output_dir / 'results.csv', output_dir / 'results.md'))


if __name__ == '__main__':
    main()
