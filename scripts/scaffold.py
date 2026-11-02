#!/usr/bin/env python3
"""Preview or copy the bundled workspace templates; never overwrite a target.

Python 3.9+, standard library only. No network, subprocesses, credentials, or
runtime deployment. Path checks are anti-footgun measures, not a security sandbox.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Dict, Any


def safe_target(raw: str) -> Path:
    target = Path(raw).expanduser()
    if not target.is_absolute():
        raise ValueError('Use an explicit absolute target path.')
    if '..' in target.parts:
        raise ValueError('Parent traversal (..) is not accepted.')
    for part in (target,) + tuple(target.parents):
        if part.is_symlink():
            raise ValueError('A target or parent is a symbolic link; choose a direct path.')
    if target.exists():
        raise ValueError('Target already exists. Read its state and plan a migration; it will not be overwritten.')
    if not target.parent.is_dir():
        raise ValueError('Target parent must already exist. No parent directories are created automatically.')
    if target == Path(target.anchor) or target == Path.home():
        raise ValueError('A root or home directory cannot be the workspace target.')
    return target


def scaffold(raw: str, apply: bool = False) -> Dict[str, Any]:
    target = safe_target(raw)
    source = Path(__file__).resolve().parent.parent / 'assets' / 'workspace'
    if not source.is_dir():
        raise ValueError('Bundled workspace templates are missing. Use the full skill folder.')
    paths = sorted(source.rglob('*'))
    if any(p.is_symlink() for p in paths):
        raise ValueError('Bundled templates contain a symbolic link. Stop and inspect the package.')
    files = [p.relative_to(source).as_posix() for p in paths if p.is_file()]
    if not files:
        raise ValueError('No bundled template files were found.')
    result = {'mode': 'APPLY' if apply else 'PREVIEW', 'target': str(target),
              'files': files, 'file_count': len(files),
              'note': 'Templates only. No task was approved or run, and no service was installed.'}
    if apply:
        # copytree without dirs_exist_ok refuses a concurrently created target.
        # An I/O failure may leave a partial new directory; never remove it blindly.
        shutil.copytree(source, target, symlinks=False)
        result['created'] = True
    else:
        result['created'] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', help='Absolute path of a new workspace; its parent must already exist.')
    parser.add_argument('--apply', action='store_true', help='Copy templates after the user has approved this exact scope.')
    args = parser.parse_args()
    try:
        print(json.dumps(scaffold(args.target, args.apply), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({'status':'ERROR','message':str(exc),
                          'note':'No automatic rollback or deletion is performed. Inspect a partial target before retrying.'},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
