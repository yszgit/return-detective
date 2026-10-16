"""Prepare a separate local view of a saved cloud rehearsal; make no AWS calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='new directory under runtime/')
    args = parser.parse_args()
    source = args.snapshot.resolve()
    output = args.out.resolve()
    runtime = (ROOT / 'runtime').resolve()
    if output == runtime or not output.is_relative_to(runtime):
        parser.error('Output must be a separate directory inside this repository runtime/.')
    if (output / 'cases.json').exists():
        parser.error('The target already has cases. Choose a new replay directory.')
    raw = source.read_bytes()
    snapshot = json.loads(raw)
    if not isinstance(snapshot.get('cases'), dict) or not snapshot['cases']:
        parser.error('A nonempty saved case snapshot is required.')
    os.environ.update(RD_BACKEND='duckdb', RD_DATASET_VERSION='2', RD_DATA_DIR=str(ROOT / 'data/cleaned'),
        RD_STORE_BACKEND='json', RD_STATE_TABLE='', RD_RUNTIME_DIR=str(output),
        RD_STORE_NAMESPACE=output.name, RD_MODEL_ID='', RD_FAST_MODEL_ID='', RD_RECORDED_REPLAY='1')
    sys.path.insert(0, str(ROOT))
    from rd import store, workflow
    store.restore(snapshot)
    as_of = workflow.latest_case_date(snapshot['cases'].values())
    report = workflow.process_day(as_of)
    destination = output / 'traces' / workflow.source_key()
    destination.mkdir(parents=True, exist_ok=True)
    for path in (source.parent / 'traces').glob('*/run-*.json'):
        trace = json.loads(path.read_text(encoding='utf-8'))
        if trace.get('case_id') not in snapshot['cases']:
            continue
        trace['recorded_from_source_key'] = trace.get('source_key')
        trace.update(source_key=workflow.source_key(), namespace=store._NAMESPACE, recorded_replay=True)
        (destination / path.name).write_text(json.dumps(trace, default=str, ensure_ascii=False), encoding='utf-8')
    (output / 'replay-provenance.json').write_text(json.dumps({
        'source_snapshot_sha256': hashlib.sha256(raw).hexdigest(), 'as_of': as_of,
        'model_calls_during_preparation': 0, 'recorded_view': True}, indent=2), encoding='utf-8')
    print(json.dumps({'prepared': str(output), 'cases': len(snapshot['cases']),
                      'as_of': as_of, 'model_calls': 0, 'records': report['counts']['total']}))


if __name__ == '__main__':
    main()
