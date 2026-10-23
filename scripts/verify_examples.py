#!/usr/bin/env python3
"""Build and run the complete programs readers copy from the site.

Every block marked `<!-- roplat-example: NAME -->` ... `<!-- /roplat-example -->`
becomes `src/bin/NAME.rs` of a fresh Cargo project made from validation/Cargo.toml
and validation/Cargo.lock (roplat from crates.io). Each program must exit with
success; a block marked `<!-- roplat-output: NAME -->` must equal its stdout.
Clippy with `-D warnings` and rustfmt then check all programs together.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

EXAMPLE = re.compile(
    r'<!-- roplat-example: ([a-z0-9-]+) -->\s*```rust\n(.*?)\n```\s*<!-- /roplat-example -->', re.S)
OUTPUT = re.compile(
    r'<!-- roplat-output: ([a-z0-9-]+) -->\s*```text\n(.*?)\n```\s*<!-- /roplat-output -->', re.S)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def collect(docs):
    examples, outputs = {}, {}
    for page in sorted(docs.rglob('*.md')):
        text = page.read_text(encoding='utf-8')
        for pattern, found in ((EXAMPLE, examples), (OUTPUT, outputs)):
            for name, body in pattern.findall(text):
                if name in found:
                    sys.exit(f'duplicate marker {name!r} in {page}')
                found[name] = (page, body)
    missing = sorted(set(outputs) - set(examples))
    if missing:
        sys.exit(f'output blocks without a program: {missing}')
    return examples, outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--offline', action='store_true', help='pass --offline to Cargo')
    parser.add_argument('--only', action='append', default=[], help='check only this program')
    parser.add_argument('--update-lock', action='store_true',
                        help='re-resolve validation/Cargo.lock instead of using it')
    parser.add_argument('--record', action='store_true',
                        help='write the summary to validation/examples.json')
    args = parser.parse_args()

    site = Path(__file__).resolve().parents[1]
    examples, outputs = collect(site / 'docs')
    if args.only:
        unknown = sorted(set(args.only) - set(examples))
        if unknown:
            sys.exit(f'unknown programs: {unknown}')
        examples = {name: examples[name] for name in args.only}
    if not examples:
        sys.exit('no marked programs found')

    work = Path(tempfile.mkdtemp(prefix='roplat-pages-examples-'))
    (work / 'src/bin').mkdir(parents=True)
    shutil.copyfile(site / 'validation/Cargo.toml', work / 'Cargo.toml')
    lock = site / 'validation/Cargo.lock'
    if not args.update_lock:
        shutil.copyfile(lock, work / 'Cargo.lock')
    for name, (_, source) in examples.items():
        (work / 'src/bin' / f'{name}.rs').write_text(source + '\n', encoding='utf-8')

    cargo = ['cargo']
    flags = ['--offline'] if args.offline else []
    summary = {
        'roplat': '0.5.0 (crates.io)',
        'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(),
        'programs': {},
        'checks': [],
    }

    def run(label, command, capture=False):
        proc = subprocess.run(command, cwd=work, text=True, capture_output=True)
        (work / f'{label}.log').write_text(proc.stdout + proc.stderr, encoding='utf-8')
        summary['checks'].append({'name': label, 'returncode': proc.returncode})
        print(f'{label}: {"PASS" if proc.returncode == 0 else "FAIL"}', flush=True)
        if proc.returncode:
            print(proc.stderr[-8000:])
            sys.exit(f'failed; logs kept in {work}')
        return proc.stdout

    if args.update_lock:
        run('lock', cargo + ['generate-lockfile'] + flags)
        shutil.copyfile(work / 'Cargo.lock', lock)
    locked = flags + ['--locked']
    run('build', cargo + ['build', '--bins'] + locked)
    for name, (page, source) in examples.items():
        stdout = run(name, cargo + ['run', '-q', '--bin', name] + locked, capture=True)
        if name in outputs:
            expected = outputs[name][1].rstrip()
            if stdout.rstrip() != expected:
                print(f'--- expected\n{expected}\n--- actual\n{stdout.rstrip()}')
                sys.exit(f'{name}: output differs from the page; logs kept in {work}')
        summary['programs'][name] = {
            'page': str(page.relative_to(site)),
            'source_sha256': sha256(source.encode()),
            'output_checked': name in outputs,
        }
    run('clippy', cargo + ['clippy', '--bins'] + locked + ['--', '-D', 'warnings'])
    run('fmt', cargo + ['fmt', '--', '--check'])
    summary['lock_sha256'] = sha256(lock.read_bytes())
    (work / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    if args.record:
        (site / 'validation/examples.json').write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'{len(examples)} programs passed; logs in {work}')


if __name__ == '__main__':
    main()
