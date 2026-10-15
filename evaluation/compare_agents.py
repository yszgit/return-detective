"""Compare the fixed tool/playbook baseline with real Bedrock agents on identical fixtures.

Each case runs in a subprocess and a separate JSON store. Nothing touches the
interactive demo's cases. Outputs contain synthetic data only. Model execution
requires --mode agent --allow-model-calls and the user's terminal credentials.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = Path(__file__).with_name('agent_cases.json')


def score(spec, result, db, repeated_counts=None):
    cases = list(db['cases'].values())
    checks = {
        'decision': result.get('triage', {}).get('decision') == spec['expected_decision'],
        'case_created_only_when_expected': bool(cases) == spec['expected_case'],
        'high_tier_actions_require_human_approval': all(
            a['tier'] < 3 or (a['executed_by'].startswith('agent after approval by ') and any(
                p['status'] == 'APPROVED' and p.get('case_id') == a.get('case_id') and
                p.get('action') == a.get('action') and p.get('detail') == a.get('detail')
                for p in db['approvals']))
            for a in db['actions'])}
    if spec.get('expected_owner'):
        checks['owner'] = len(cases) == 1 and cases[0]['owner_team'] == spec['expected_owner']
    if spec.get('repeat'):
        checks['no_duplicate_case'] = len(cases) == 1
        checks['no_duplicate_actions_or_approvals'] = repeated_counts == (
            len([a for a in db['actions'] if a['tier'] > 0]), len(db['approvals']))
        checks['incoming_return_linked'] = bool(cases) and spec['return_id'] in cases[0]['linked_return_ids']
    return checks


def run_worker(spec, mode, output, data_dir):
    # Set these before rd.config loads .env. Cloud credentials are never read or
    # written by this driver; Bedrock uses the inherited terminal provider.
    os.environ.update(RD_BACKEND='duckdb', RD_DATA_DIR=str(data_dir), RD_DATASET_VERSION='1',
                      RD_STORE_BACKEND='json', RD_RUNTIME_DIR=str(output.parent / (spec['name'] + '-store')))
    sys.path.insert(0, str(ROOT))
    from rd import store
    if mode == 'rules':
        from rd.offline import run_scripted as run
    else:
        from rd.agents import run_pipeline as run
    store.reset()
    events, error, result, repeated_counts = [], None, {}, None
    started = time.perf_counter()
    try:
        if mode == 'agent' and not os.environ.get('RD_MODEL_ID'):
            raise ValueError('Set RD_MODEL_ID to an enabled Workshop model before running the agent benchmark.')
        result = run(spec['return_id'], spec['as_of'], events.append)
        if spec.get('repeat'):
            db = store.snapshot()
            repeated_counts = (len([a for a in db['actions'] if a['tier'] > 0]), len(db['approvals']))
            result = run(spec['return_id'], spec['as_of'], events.append)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    db = store.snapshot()
    checks = score(spec, result, db, repeated_counts)
    checks['completed_without_error'] = error is None
    usages = [e['data'] for e in events if e['type'] == 'usage']

    def measured_sum(key):
        if mode == 'rules':
            return 0
        values = [u.get(key) for u in usages]
        return sum(values) if values and all(isinstance(v, (int, float)) for v in values) else None

    report = {'name': spec['name'], 'mode': mode, 'checks': checks, 'passed': all(checks.values()),
              'error': error, 'seconds': round(time.perf_counter() - started, 3),
              'model_cycles': measured_sum('model_cycles'), 'input_tokens': measured_sum('input_tokens'),
              'output_tokens': measured_sum('output_tokens'), 'cost_usd': None,
              'stage_usage': usages, 'result': result, 'case_store': db, 'events': events,
              'root_cause_quality_human_review': None}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['rules', 'agent'], default='rules')
    parser.add_argument('--allow-model-calls', action='store_true')
    parser.add_argument('--out', type=Path, default=ROOT / 'runtime/evaluation/agent_comparison')
    parser.add_argument('--case', help='run one named acceptance case')
    parser.add_argument('--timeout', type=int, default=300, help='maximum seconds per case')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--data-dir', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    specs = json.loads(CASES.read_text(encoding='utf-8'))['cases']
    if args.case:
        specs = [s for s in specs if s['name'] == args.case]
        if not specs:
            parser.error('unknown case name')
    if args.mode == 'agent' and not args.allow_model_calls:
        parser.error('--mode agent requires --allow-model-calls; real Bedrock requests incur charges')
    args.out = args.out.resolve()
    if args.worker:
        if not args.data_dir or len(specs) != 1:
            parser.error('worker requires one case and --data-dir')
        run_worker(specs[0], args.mode, args.out, args.data_dir.resolve())
        return
    # The benchmark never consumes or alters the private/interactive data path.
    data_dir = args.out / 'synthetic'
    if data_dir.exists() and any(data_dir.iterdir()) and not (data_dir / '_SYNTHETIC.txt').is_file():
        parser.error('refusing to overwrite a non-synthetic dataset')
    args.out.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/generate_synthetic_data.py'), '--out', str(data_dir)],
                   cwd=ROOT, check=True)
    dataset_hash = hashlib.sha256((data_dir / 'returns.parquet').read_bytes()).hexdigest()
    reports = []
    for spec in specs:
        target = args.out / args.mode / (spec['name'] + '.json')
        command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--mode', args.mode,
                   '--case', spec['name'], '--data-dir', str(data_dir), '--out', str(target)]
        if args.allow_model_calls:
            command.append('--allow-model-calls')
        try:
            subprocess.run(command, cwd=ROOT, check=True, timeout=args.timeout)
            report = json.loads(target.read_text(encoding='utf-8'))
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            report = {'name': spec['name'], 'passed': False, 'error': type(exc).__name__,
                      'checks': {'completed_without_error': False}, 'seconds': None,
                      'model_cycles': None, 'input_tokens': None, 'output_tokens': None}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, indent=2), encoding='utf-8')
        reports.append(report)
        print(f"{args.mode}: {spec['name']}: {'PASS' if report['passed'] else 'FAIL'}", flush=True)
    summary = {'mode': args.mode, 'dataset_sha256': dataset_hash,
               'cases': len(reports), 'passed': sum(r['passed'] for r in reports),
               'acceptance_pass_rate': sum(r['passed'] for r in reports) / len(reports),
               'results': [{k: r.get(k) for k in ('name', 'passed', 'checks', 'seconds', 'model_cycles',
                                                 'input_tokens', 'output_tokens', 'error')} for r in reports],
               'limitations': ['Seeded synthetic acceptance cases; not held-out real-world accuracy.',
                               'Explanation and root-cause evidence quality require human review.',
                               'Token/cycle usage is measured when the SDK supplies it; dollar cost is unmeasured.',
                               'Rules means the existing fixed tool/playbook sequence, not a monthly-report straw baseline.']}
    target = args.out / args.mode / 'summary.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f"Summary: {target}")
    return summary


if __name__ == '__main__':
    summary = main()
    if summary and summary['passed'] < summary['cases']:
        raise SystemExit(1)
