#!/usr/bin/env python3
"""Read-only, partial consistency check of a bootstrap workspace.

This is not an authorization service, sandbox test, task runner or quality judge.
PASS means only that the checks implemented here found no contradiction.
Python 3.9+, standard library only; no network or subprocess calls.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
from typing import Dict, Any, List

STAGES = {f'S{i}' for i in range(7)}
STATES = {'DRAFT','READY','RUNNING','BLOCKED','VERIFYING','DELIVERING','DONE','FAILED','CANCELLED'}
CAPS = {'VERIFIED','UNKNOWN','UNSUPPORTED','HUMAN'}
MAX_RECORD_BYTES = 1_048_576
MAX_ARTIFACT_BYTES = 20_971_520


def checked_file(root: Path, relative: str, max_size: int = MAX_RECORD_BYTES) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError('A nonempty relative file reference is required.')
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Reference must stay inside the workspace.')
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symbolic-link references are not inspected.')
    try:
        current.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError('Reference escapes the workspace.')
    info = current.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Reference is not a regular file.')
    if info.st_size > max_size:
        raise ValueError(f'File exceeds inspection limit ({max_size} bytes).')
    return current


def reject_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('Duplicate JSON key: ' + key)
        out[key] = value
    return out


def read_object(root: Path, relative: str) -> Dict[str, Any]:
    value = json.loads(checked_file(root, relative).read_text(encoding='utf-8'),
                       object_pairs_hook=reject_duplicate_keys)
    if not isinstance(value, dict):
        raise ValueError('JSON root must be an object.')
    return value


def check_workspace(raw: str) -> Dict[str, Any]:
    root = Path(raw).expanduser()
    if not root.is_absolute():
        raise ValueError('Use an absolute workspace path.')
    if '..' in root.parts or any(p.is_symlink() for p in (root,) + tuple(root.parents)):
        raise ValueError('Workspace and parents must not use traversal or symbolic links.')
    if not root.is_dir():
        raise ValueError('Workspace directory does not exist.')
    errors: List[str] = []
    warnings: List[str] = ['Only partial record consistency is checked; this does not prove authorization, safety, quality or deployment.']

    def error(message: str):
        errors.append(message)

    def record(rel: str):
        try:
            return read_object(root, rel)
        except (ValueError, OSError, UnicodeError) as exc:
            error(rel + ': ' + str(exc))
            return {}

    def reference(ref: Any, label: str, max_size: int = MAX_RECORD_BYTES):
        try:
            return checked_file(root, ref, max_size)
        except (ValueError, OSError, TypeError) as exc:
            error(label + ': ' + str(exc))
            return None

    build = record('BUILD_STATE.json')
    policy = record('control/policy.json')
    capabilities = record('control/capabilities.json')
    for name, item in [('build',build),('policy',policy),('capabilities',capabilities)]:
        if item.get('schema_version') != 1:
            error(name + ': unsupported or missing schema_version.')
    if build.get('stage') not in STAGES:
        error('build: unknown stage.')
    if build.get('stage_status') not in {'NOT_STARTED','IN_PROGRESS','AWAITING_APPROVAL','BLOCKED','COMPLETE'}:
        error('build: unknown stage_status.')
    if build.get('runtime_level') not in {'M0','M1','M2'}:
        error('build: unknown runtime_level.')
    if not isinstance(build.get('next_action'),str) or not build['next_action'].strip():
        error('build: next_action is required.')
    for name in ['max_parallel','max_attempts','max_review_rounds']:
        val=policy.get(name)
        if type(val) is not int or val < 1:
            error('policy: ' + name + ' must be a positive integer.')
    mode = policy.get('execution_mode')
    if mode not in {'simulate','assisted','bounded_auto'}:
        error('policy: unknown execution_mode.')
    for name in ['external_actions_enabled','automatic_dispatch','limits_are_enforced']:
        if type(policy.get(name)) is not bool:
            error('policy: ' + name + ' must be boolean.')
    if mode == 'simulate':
        if policy.get('external_actions_enabled') is not False or policy.get('automatic_dispatch') is not False:
            error('policy: simulate must disable external actions and automatic dispatch.')
    if policy.get('approval_status') not in {'PENDING','APPROVED','REJECTED','EXPIRED','REVOKED'}:
        error('policy: unknown approval_status.')
    if policy.get('approval_status') == 'APPROVED':
        reference(policy.get('approval_ref'), 'policy approval_ref')
    else:
        warnings.append('Policy is not approved; creating templates did not authorize execution.')
    if mode == 'bounded_auto':
        if policy.get('approval_status') != 'APPROVED':
            error('policy: bounded_auto requires an approval record.')
        reference(policy.get('automation_evidence_ref'), 'policy automation_evidence_ref')
        warnings.append('Automation evidence is only located, not evaluated or authenticated.')
    if policy.get('cost_measurement') == 'UNKNOWN':
        warnings.append('Cost is not measured; no monetary spending cap is proven.')
    cap_list = capabilities.get('capabilities')
    if not isinstance(cap_list, list):
        error('capabilities: capabilities must be an array.')
        cap_list=[]
    for cap in cap_list:
        if not isinstance(cap,dict) or cap.get('status') not in CAPS:
            error('capabilities: invalid capability record.')
            continue
        if cap.get('status') == 'VERIFIED':
            reference(cap.get('evidence_ref'), 'capability ' + str(cap.get('name')))
    if build.get('stage') == 'S6' and build.get('stage_status') == 'COMPLETE':
        gates=build.get('gates',{})
        for name in ['scope','plan','scaffold','pilot','recovery','handover']:
            gate=gates.get(name) if isinstance(gates,dict) else None
            if not isinstance(gate,dict) or gate.get('status')!='PASS':
                error('build completion: missing passed gate ' + name)
            else:
                reference(gate.get('evidence_ref'), 'build gate ' + name)
    tasks = root / 'tasks'
    task_count = 0
    if tasks.is_symlink():
        error('tasks: symbolic links are not inspected.')
    elif tasks.is_dir():
        for folder in sorted(tasks.iterdir()):
            if folder.is_symlink():
                error('tasks: symbolic link entry is not inspected.')
                continue
            if not folder.is_dir():
                continue
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',folder.name):
                error('tasks: unsupported task directory name.')
                continue
            task_count+=1
            task=record(f'tasks/{folder.name}/state.json')
            state=task.get('state')
            if task.get('task_id') != folder.name:
                error(folder.name + ': task_id differs from directory name.')
            if state not in STATES:
                error(folder.name + ': unknown task state.')
            if state == 'BLOCKED':
                for key in ['block_reason','resume_state','resume_condition']:
                    if not task.get(key):
                        error(folder.name + ': BLOCKED requires ' + key)
            ops=task.get('external_operations',[])
            if not isinstance(ops,list):
                error(folder.name + ': external_operations must be an array.')
                ops=[]
            unknown=False
            for op in ops:
                if not isinstance(op,dict):
                    error(folder.name + ': invalid operation record.'); continue
                if op.get('status') not in {'PLANNED','AUTHORIZED','ATTEMPTED','CONFIRMED','NOT_APPLIED','UNKNOWN'}:
                    error(folder.name + ': unknown external-operation status.')
                if op.get('status')=='UNKNOWN':
                    unknown=True
                    if op.get('retry_planned') is True:
                        error(folder.name + ': UNKNOWN external action must not be blindly retried.')
            if state == 'DONE':
                if unknown:
                    error(folder.name + ': DONE conflicts with UNKNOWN external effects.')
                review=task.get('review',{})
                if not isinstance(review,dict) or review.get('verdict')!='PASS':
                    error(folder.name + ': DONE requires a PASS review record.')
                    review={}
                if review.get('kind') not in {'SELF_CHECK','INDEPENDENT_REVIEW','REPRODUCIBLE_TEST','SPECIALIST_REVIEW'}:
                    error(folder.name + ': DONE requires the actual review kind.')
                artifact=reference(task.get('artifact'),folder.name + ' artifact', MAX_ARTIFACT_BYTES)
                reference(review.get('evidence_ref'),folder.name + ' review evidence')
                reference(task.get('delivery_ref'),folder.name + ' delivery evidence')
                if artifact:
                    digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
                    if task.get('artifact_sha256') != digest:
                        error(folder.name + ': artifact hash does not match the reviewed version.')
    else:
        error('tasks: directory is missing.')
    if task_count == 0:
        error('No task records were found.')
    return {'status':'FAIL' if errors else 'PASS','scope':'PARTIAL_RECORD_CONSISTENCY_ONLY',
            'task_count':task_count,'errors':errors,'warnings':warnings,
            'does_not_verify':['human approval authenticity','OS or tool isolation','report correctness',
                               'actual external receipts','state transition history','running process status']}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace',help='Absolute workspace path')
    args=parser.parse_args()
    try:
        result=check_workspace(args.workspace)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result['errors'] else 0
    except (ValueError,OSError) as exc:
        print(json.dumps({'status':'ERROR','message':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2


if __name__=='__main__':
    sys.exit(main())
