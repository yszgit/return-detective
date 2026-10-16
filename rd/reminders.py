"""Durable, opt-in review emails through EventBridge Scheduler and the team SNS topic.

SNS broadcasts to the topic's subscribers. Calendar contacts are notes, not email
routing. Scheduling acceptance does not establish execution or inbox delivery.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re

from . import store


def settings():
    topic = os.environ.get('RD_SNS_TOPIC_ARN', '').strip()
    role = os.environ.get('RD_SCHEDULER_ROLE_ARN', '').strip()
    group = os.environ.get('RD_SCHEDULER_GROUP', 'return-detective-reviews').strip()
    match = re.fullmatch(r'arn:(aws(?:-us-gov|-cn)?):sns:([a-z0-9-]+):(\d{12}):([A-Za-z0-9_-]+)', topic)
    if not match or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', group):
        raise ValueError('Configure a Standard RD_SNS_TOPIC_ARN and a valid RD_SCHEDULER_GROUP.')
    partition, region, account, _ = match.groups()
    if not re.fullmatch(rf'arn:{partition}:iam::{account}:role/[A-Za-z0-9_+=,.@/\-]+', role):
        raise ValueError('Set RD_SCHEDULER_ROLE_ARN to the review reminder execution role in this account.')
    return dict(topic_arn=topic, role_arn=role, group=group, region=region, partition=partition)


def configured():
    try:
        settings()
        return True
    except ValueError:
        return False


def _client(service, region):
    import boto3
    from botocore.config import Config
    return boto3.client(service, region_name=region,
                        config=Config(connect_timeout=5, read_timeout=10, retries={'total_max_attempts': 2}))


def _code(exc):
    return getattr(exc, 'response', {}).get('Error', {}).get('Code') or type(exc).__name__


def recipients(config=None):
    config = config or settings()
    client = _client('sns', config['region'])
    result, token = [], None
    while True:
        args = dict(TopicArn=config['topic_arn'])
        if token:
            args['NextToken'] = token
        page = client.list_subscriptions_by_topic(**args)
        for sub in page.get('Subscriptions', []):
            if sub['Protocol'] not in ('email', 'email-json') or sub['SubscriptionArn'] == 'PendingConfirmation':
                continue
            attrs = client.get_subscription_attributes(SubscriptionArn=sub['SubscriptionArn'])['Attributes']
            if json.loads(attrs.get('FilterPolicy') or '{}'):
                raise ValueError('An SNS email subscription has a filter policy. Review it before enabling reminder delivery.')
            result.append(sub['Endpoint'])
        token = page.get('NextToken')
        if not token:
            break
    if not result:
        raise ValueError('No confirmed SNS email subscriber. Confirm the subscription before scheduling a reminder.')
    return sorted(set(result))


def _name(case_id):
    identity = [store.STORE_BACKEND, store.STATE_TABLE or store._TABLES, store._NAMESPACE, case_id]
    if store.STORE_BACKEND == 'json':
        identity.append(str(Path(store._PATH).resolve()))
    return 'rd-review-' + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:40]


def cancel(case):
    """Cancel the tracked job before a plan is replaced or its case is deleted."""
    plan = case.get('review_plan') or {}
    reminder = plan.get('reminder') or {}
    if not reminder.get('name') or plan.get('email_delivery') == 'CANCELLED':
        return plan
    if reminder['name'] != _name(case['case_id']) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', reminder.get('group', '')):
        raise ValueError('Reminder identity does not match this workspace; cancellation was stopped.')
    client = _client('scheduler', reminder['region'])
    try:
        client.delete_schedule(Name=reminder['name'], GroupName=reminder['group'])
    except Exception as exc:
        if _code(exc) != 'ResourceNotFoundException':
            raise ValueError('Could not cancel the AWS reminder: ' + _code(exc)) from None
    changed = {**plan, 'email_delivery': 'CANCELLED',
               'reminder': {**reminder, 'state': 'CANCELLED',
                            'cancelled_at': dt.datetime.now(dt.timezone.utc).isoformat()}}
    if not store.update_case(case['case_id'], review_plan=changed):
        raise ValueError('The reminder was cancelled in AWS but its case record could not be updated.')
    return changed


def schedule(case, plan, *, now=None):
    if os.environ.get('RD_RECORDED_REPLAY') == '1':
        raise ValueError('Recorded replay cannot schedule real emails.')
    config = settings()
    now = now or dt.datetime.now(dt.timezone.utc)
    due = dt.datetime.fromisoformat(plan['review_at_utc']).astimezone(dt.timezone.utc)
    if due < now + dt.timedelta(minutes=1):
        raise ValueError('Choose a reminder time at least one minute in the future.')
    confirmed = recipients(config)
    # Replacing a plan never leaves the older schedule enabled at another time.
    cancel(case)
    meta = {**config, 'name': _name(case['case_id']), 'state': 'PREPARING',
            'confirmed_recipients': confirmed}
    plan = {**plan, 'email_delivery': 'PREPARING', 'reminder': meta}
    if not store.update_case(case['case_id'], review_plan=plan):
        raise ValueError('Could not save the reminder intent; no AWS schedule was created.')
    payload = {
        'TopicArn': config['topic_arn'],
        'Subject': f'Return Detective: review due for {case["case_id"]}',
        'Message': '\n'.join([
            'Return Detective: a planned case review is due.',
            f'Case: {case["case_id"]}', f'Product: {case["style"]}', f'Issue: {case["category"]}',
            f'Planned review: {plan["local_at"]} ({plan["timezone"]})',
            f'Workspace: {store._NAMESPACE or "local"}',
            'Open Approvals & follow-up in Return Detective and select this case.',
            'Check the current case status; it may already have been resolved.',
            'This is a reminder only. No Agent run, approval or retail action was executed.',
        ])}
    args = dict(Name=meta['name'], GroupName=config['group'],
                Description=f'Return Detective review: {case["case_id"]}',
                ScheduleExpression=f'at({due.strftime("%Y-%m-%dT%H:%M:%S")})',
                ScheduleExpressionTimezone='UTC', FlexibleTimeWindow={'Mode': 'OFF'},
                ActionAfterCompletion='DELETE', State='ENABLED',
                Target={'Arn': f'arn:{config["partition"]}:scheduler:::aws-sdk:sns:publish',
                        'RoleArn': config['role_arn'], 'Input': json.dumps(payload),
                        'RetryPolicy': {'MaximumEventAgeInSeconds': 3600, 'MaximumRetryAttempts': 3}})
    try:
        client = _client('scheduler', config['region'])
        try:
            client.get_schedule(Name=meta['name'], GroupName=config['group'])
        except Exception as exc:
            if _code(exc) != 'ResourceNotFoundException':
                raise
            response = client.create_schedule(**args)
        else:
            response = client.update_schedule(**args)
        check = client.get_schedule(Name=meta['name'], GroupName=config['group'])
        if any(check.get(key) != args[key] for key in ('ScheduleExpression', 'State', 'Target')):
            raise ValueError('AWS schedule verification did not match the requested reminder.')
        meta.update(state='SCHEDULED', schedule_arn=response['ScheduleArn'])
        plan['email_delivery'] = 'SCHEDULED'
    except Exception as exc:
        meta.update(state='UNCONFIRMED', error=_code(exc))
        plan['email_delivery'] = 'UNCONFIRMED'
    if not store.update_case(case['case_id'], review_plan=plan):
        raise ValueError('AWS reminder state could not be saved. Inspect the recorded reminder intent before retrying.')
    return plan
