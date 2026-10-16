"""Deterministic labels for recorded tool use; no model-generated reasoning."""
from collections import defaultdict, deque
import datetime as dt
import json


PURPOSES = {
    'read_playbook': 'Read authority and response rules',
    'style_reason_mix': 'Compare return categories',
    'weekly_timeline': 'Check persistence over time',
    'spread_analysis': 'Check stores, channels and SKUs',
    'sample_returns': 'Inspect recent return records',
    'sku_return_rate': 'Check sales denominator coverage',
    'fee_audit': 'Check fee evidence and its limits',
    'exchange_evidence': 'Check order-level exchange evidence',
    'transaction_context': 'Check dated transaction context',
    'read_case': 'Read previous findings and decisions',
    'open_case': 'Open or reuse the case',
    'record_findings': 'Save the assessment',
    'notify_owner_team': 'Record owner notification (simulation)',
    'waive_restocking_fees': 'Apply the fee authority gate (simulation)',
    'request_fit_guidance_update': 'Request Merchandising approval for fit guidance',
    'request_stock_hold': 'Request human approval for a stock hold',
    'draft_supplier_claim': 'Draft a claim for human approval',
    'request_proactive_outreach': 'Request human approval for outreach',
    'schedule_verification': 'Record the historical verification date',
}


def window_label(as_of, days):
    end = dt.date.fromisoformat(as_of)
    start = end - dt.timedelta(days=int(days) - 1)
    return f'{days} days · {start} to {end} (inclusive)'


def cutoff(trace):
    result = trace.get('result') or {}
    if trace.get('as_of') or result.get('as_of'):
        return trace.get('as_of') or result['as_of']
    for event in trace.get('events', []):
        data = event.get('data') or {}
        if event.get('type') == 'decision':
            value = data.get('now', {}).get('as_of') or data.get('as_of')
            if value:
                return value
    return None


def _scope(name, args, as_of, case):
    style = args.get('style') or case.get('style', 'Selected style')
    category = args.get('category') or case.get('category', 'Selected category')
    through = f'through {as_of}' if as_of else 'cutoff not recorded'
    category_scope = 'all return categories' if name in ('style_reason_mix', 'sku_return_rate', 'exchange_evidence', 'transaction_context') else category
    prefix = f'{style} · {category_scope} · all supplied channels / banners'
    days = None
    if name in ('style_reason_mix', 'transaction_context'):
        days = args.get('days', 90)
    elif name == 'spread_analysis':
        days = args.get('days', 60)
    elif name == 'weekly_timeline':
        days = int(args.get('weeks', 16)) * 7
    if days:
        return f'{prefix} · ' + (window_label(as_of, days) if as_of else f'{days} days; cutoff not recorded')
    if name == 'sample_returns':
        return f'{prefix} · latest {args.get("limit", 12)} records {through}; sample, not a total'
    if name in ('fee_audit', 'sku_return_rate', 'exchange_evidence'):
        grain = 'distinct return transactions' if name == 'fee_audit' else 'order-linked exchange lines' if name == 'exchange_evidence' else 'SKU / partial sales coverage'
        return f'{prefix} · supplied history {through} · {grain}'
    if name == 'read_playbook':
        return 'Response policy; no return count'
    return f'Case {case.get("case_id", "record")} · recorded prototype action; not a return count'


def _outcome(event):
    if not event:
        return 'Result not recorded'
    try:
        result = json.loads(event.get('output', ''))
    except (ValueError, TypeError):
        result = None
    if isinstance(result, dict):
        if result.get('error'):
            return 'Blocked · ' + str(result['error'])[:180]
        if result.get('refused'):
            return 'Not authorized · ' + str(result['refused'])[:180]
        if result.get('approval_status') in ('APPROVED', 'REJECTED'):
            return 'Existing proposal · ' + result['approval_status'].lower()
        if result.get('approval_required') or result.get('status') == 'PENDING' or result.get('approval_status') == 'PENDING':
            return 'Human approval required'
        if result.get('population_return_rate_available') is False:
            return 'Population return rate unavailable'
        if result.get('historical_fee_evidence_available') is False:
            return 'Historical fee evidence withheld'
    return 'Tool error' if event.get('status') == 'error' else 'Result recorded'


def _count_summary(name, event, args, case):
    try:
        result = json.loads(event.get('output', ''))
    except (ValueError, TypeError):
        return None
    category = args.get('category') or case.get('category')
    if name == 'style_reason_mix' and isinstance(result, dict):
        match = next((r for r in result.get('mix', []) if r.get('category') == category), None)
        if match:
            return f"{match['n']} {category} / {result['total_returns']} total return records"
    if name == 'spread_analysis' and isinstance(result, dict) and 'total' in result:
        return f"{result['total']} {category} return records"
    if name == 'fee_audit' and isinstance(result, dict) and 'related_return_transactions' in result:
        return f"{result['related_return_transactions']} related return transactions; fee amounts unavailable"
    if name == 'sample_returns' and isinstance(result, list):
        return f'{len(result)} sampled return records; not the full count'
    return None


def steps(trace, case):
    """Keep actual call order, matching repeated tools FIFO by agent and name."""
    rows, calls, pending = [], [], defaultdict(deque)
    as_of = cutoff(trace)
    for event in trace.get('events', []):
        name, agent = event.get('tool'), event.get('agent')
        if event.get('type') == 'tool_call':
            args = event.get('input') or {}
            calls.append(args)
            pending[(agent, name)].append(len(rows))
            rows.append({'Step': len(rows) + 1, 'Agent': agent, 'Tool': name,
                         'Purpose': PURPOSES.get(name, 'Recorded tool call'),
                         'Evidence scope': _scope(name, args, as_of, case),
                         'Outcome': 'Result not recorded'})
        elif event.get('type') == 'tool_result' and pending[(agent, name)]:
            index = pending[(agent, name)].popleft()
            rows[index]['Outcome'] = _outcome(event)
            # Keep numeric evidence tied to the matched call, including repeated tools.
            summary = _count_summary(name, event, calls[index], case)
            if summary:
                rows[index]['Observed count'] = summary
    return rows
