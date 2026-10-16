"""Immediate internal case alerts. SNS acceptance does not prove email delivery.

The workflow serializes calls within one process. Standard SNS can redeliver;
this marker is not an exactly-once guarantee across workers or network failures.
"""
import datetime as dt
import os

from . import store


def notify_case(case_id, *, scripted=False, retry=False):
    case = store.get_case(case_id)
    if case is None:
        raise ValueError('The case must be saved before notifying its owner.')
    if scripted or os.environ.get('RD_RECORDED_REPLAY') == '1':
        return {'status': 'SIMULATED'}
    previous = case.get('case_notification') or {}
    if previous.get('status') in ('ACCEPTED', 'PUBLISHING'):
        return previous
    if previous and not retry:
        return previous
    topic = os.environ.get('RD_SNS_TOPIC_ARN', '').strip()
    record = {'status': 'NOT_CONFIGURED', 'topic_arn': topic,
              'attempted_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    if not topic:
        store.update_case(case_id, case_notification=record)
        return record
    parts = topic.split(':')
    if len(parts) != 6 or parts[2] != 'sns' or not parts[3] or parts[5].endswith('.fifo'):
        record.update(status='NOT_CONFIGURED', error='Configure a Standard SNS Topic ARN.')
        store.update_case(case_id, case_notification=record)
        return record
    record['status'] = 'PUBLISHING'
    store.update_case(case_id, case_notification=record)
    try:
        import boto3
        from botocore.config import Config
        snapshot = store.snapshot()
        pending = [a['action'] for a in snapshot['approvals']
                   if a['case_id'] == case_id and a['status'] == 'PENDING']
        message = '\n'.join([
            'Return Detective: investigation completed',
            f'Case: {case_id}',
            f'Product: {case["style"]}',
            f'Issue: {case["category"]}',
            f'Evidence cutoff: {case["opened_as_of"]}',
            f'Owner: {case.get("owner_team") or "Not assigned"}',
            f'Confidence: {case.get("confidence") or "Not assessed"}',
            'Working explanation: ' + str(case.get('root_cause') or 'See case evidence')[:1000],
            'Pending proposals: ' + ('; '.join(pending) if pending else 'None'),
            'Open Case workspace in Return Detective and select this case ID.',
            'Prototype: retail actions remain simulated. Root cause requires verification.',
        ])
        client = boto3.client('sns', region_name=parts[3],
                              config=Config(connect_timeout=5, read_timeout=15,
                                            retries={'total_max_attempts': 1}))
        response = client.publish(TopicArn=topic, Subject=f'Return Detective: {case_id} needs review',
                                  Message=message)
        record.update(status='ACCEPTED', message_id=response['MessageId'])
    except Exception as exc:
        # A timeout can happen after SNS accepted the publish. Do not auto-resend.
        record.update(status='UNCONFIRMED', error=str(exc)[:400])
    store.update_case(case_id, case_notification=record)
    return record
