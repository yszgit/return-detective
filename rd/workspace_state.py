"""Back up and clear one demo workspace; source data and other namespaces stay intact."""
import datetime as dt
import json
from pathlib import Path
import uuid

from . import store, workflow
from .config import RUNTIME_DIR


def counts(state):
    return {name: len(state[name]) for name in ('cases', 'approvals', 'actions')}


def _identity():
    return {'source_key': workflow.source_key(), 'namespace': store._NAMESPACE,
            'store_backend': store.STORE_BACKEND, 'runtime_dir': str(Path(RUNTIME_DIR).resolve())}


def _backup_dir():
    return Path(RUNTIME_DIR).resolve() / 'backups' / workflow.source_key()


def _report_dir():
    return Path(RUNTIME_DIR).resolve() / 'monitor' / workflow.source_key()


def _report_path(name):
    # A backup cannot turn a report filename into an arbitrary filesystem path.
    if name != dt.date.fromisoformat(Path(name).stem).isoformat() + '.json':
        raise ValueError('The backup contains an invalid day report name.')
    path = _report_dir() / name
    if not path.resolve().is_relative_to(_report_dir().resolve()):
        raise ValueError('The report path is outside this workspace.')
    return path


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def read_backup(path):
    path = Path(path).resolve()
    if not path.is_relative_to(_backup_dir().resolve()) or path.suffix != '.json':
        raise ValueError('Select a backup from this workspace.')
    bundle = json.loads(path.read_text(encoding='utf-8'))
    if bundle.get('version') != 1 or bundle.get('identity') != _identity():
        raise ValueError('This backup belongs to another workspace or configuration.')
    state = bundle.get('state') or {}
    if not isinstance(state.get('cases'), dict) or not all(isinstance(state.get(k), list) for k in ('actions', 'approvals')):
        raise ValueError('The backup does not contain a complete case store.')
    for report in bundle.get('day_reports', []):
        _report_path(report['name'])
        if report['content'].get('source_key') != workflow.source_key():
            raise ValueError('A day report belongs to another workspace.')
    return bundle


def latest_backup():
    for path in sorted(_backup_dir().glob('clear-*.json'), reverse=True):
        try:
            read_backup(path)
        except (OSError, ValueError, KeyError):
            continue
        return path
    return None


def clear_saved_cases():
    with workflow.exclusive_run():
        state = store.snapshot()
        reports = []
        for path in sorted(_report_dir().glob('*.json')):
            checked = _report_path(path.name)
            reports.append({'name': checked.name, 'content': json.loads(checked.read_text(encoding='utf-8'))})
        created = dt.datetime.now(dt.timezone.utc)
        path = _backup_dir() / f'clear-{created.strftime("%Y%m%dT%H%M%S%fZ")}-{uuid.uuid4().hex[:6]}.json'
        _write_json(path, {'version': 1, 'identity': _identity(), 'created_at': created.isoformat(),
                           'state': state, 'day_reports': reports})
        # Verify the persisted backup before any deletion takes place.
        read_backup(path)
        from .reminders import cancel
        cancelled = False
        for case in state['cases'].values():
            plan = case.get('review_plan') or {}
            if (plan.get('reminder') or {}).get('name') and plan.get('email_delivery') != 'CANCELLED':
                cancel(case)  # Failure stops deletion; the original backup already exists.
                cancelled = True
        if cancelled:
            bundle = read_backup(path)
            state = store.snapshot()
            bundle['state'] = state
            _write_json(path, bundle)
            read_backup(path)
        store.reset()
        if any(counts(store.snapshot()).values()):
            raise ValueError(f'Workspace clearing could not be verified. The backup is saved at {path}.')
        for report in reports:
            _report_path(report['name']).unlink(missing_ok=True)
        return {'backup_path': str(path), 'deleted': counts(state), 'day_reports_cleared': len(reports)}


def restore_backup(path):
    with workflow.exclusive_run():
        bundle = read_backup(path)
        if any(counts(store.snapshot()).values()):
            raise ValueError('Restore is available only while this workspace has no cases, approvals or actions.')
        # Restore never re-arms a past external email schedule.
        for case in bundle['state']['cases'].values():
            plan = case.get('review_plan') or {}
            if (plan.get('reminder') or {}).get('name'):
                plan['email_delivery'] = 'CANCELLED'
                plan['reminder']['state'] = 'CANCELLED'
        store.restore(bundle['state'])
        for report in bundle.get('day_reports', []):
            _write_json(_report_path(report['name']), report['content'])
        restored = store.snapshot()
        if restored != bundle['state']:
            raise ValueError('The restored state could not be verified. Keep the backup and check the connection.')
        return counts(restored)
