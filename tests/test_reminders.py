"""Durable reminder contracts with mocked AWS clients; no messages are sent."""
import contextlib
import copy
import datetime as dt
import importlib
import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError


def missing():
    return ClientError({'Error': {'Code': 'ResourceNotFoundException'}}, 'GetSchedule')


class ReminderTests(unittest.TestCase):
    now = dt.datetime(2026, 10, 16, 17, tzinfo=dt.timezone.utc)

    def setUp(self):
        self.module = importlib.import_module('rd.reminders')
        self.env = patch.dict(os.environ, RD_SNS_TOPIC_ARN='arn:aws:sns:us-east-1:123456789012:team',
            RD_SCHEDULER_ROLE_ARN='arn:aws:iam::123456789012:role/review-scheduler',
            RD_SCHEDULER_GROUP='return-detective-reviews', RD_RECORDED_REPLAY='0')
        self.env.start()
        self.addCleanup(self.env.stop)
        self.case = dict(case_id='CASE-FIXTURE', style='Fixture', category='Quality', status='OPEN')
        self.store = MagicMock(STORE_BACKEND='dynamodb', STATE_TABLE='test-state', _NAMESPACE='team-a')
        self.store._TABLES = {}
        self.store.get_case.side_effect = lambda cid: copy.deepcopy(self.case)
        def save(cid, **fields):
            self.case.update(copy.deepcopy(fields))
            return copy.deepcopy(self.case)
        self.store.update_case.side_effect = save
        self.patches = patch.object(self.module, 'store', self.store)
        self.patches.start()
        self.addCleanup(self.patches.stop)
        self.sns, self.scheduler = MagicMock(), MagicMock()
        self.sns.list_subscriptions_by_topic.return_value = {'Subscriptions': [
            {'Protocol': 'email', 'Endpoint': 'confirmed@example.com',
             'SubscriptionArn': 'arn:aws:sns:us-east-1:123456789012:team:confirmed'}]}
        self.sns.get_subscription_attributes.return_value = {'Attributes': {}}
        self.request = None
        def create(**args):
            self.request = args
            return {'ScheduleArn': 'arn:aws:scheduler:us-east-1:123456789012:schedule/group/fixture'}
        self.scheduler.create_schedule.side_effect = create
        self.scheduler.update_schedule.side_effect = create
        self.scheduler.get_schedule.side_effect = lambda **kw: copy.deepcopy(self.request) if self.request else (_ for _ in ()).throw(missing())
        self.factory = patch.object(self.module, '_client', side_effect=lambda service, region:
            self.sns if service == 'sns' else self.scheduler)
        self.factory.start()
        self.addCleanup(self.factory.stop)
        self.plan = dict(review_at_utc='2026-10-16T17:10:00+00:00', local_at='2026-10-16T13:10-04:00',
                         timezone='America/Toronto', contact_email='notes-only@example.com',
                         automatic_run=False, email_delivery='NOT_ENABLED')

    def test_utc_schedule_is_verified_and_does_not_publish_immediately(self):
        plan = self.module.schedule(self.case, self.plan, now=self.now)
        self.assertEqual(plan['email_delivery'], 'SCHEDULED')
        self.assertEqual(self.request['ScheduleExpression'], 'at(2026-10-16T17:10:00)')
        self.assertEqual(self.request['ScheduleExpressionTimezone'], 'UTC')
        self.assertEqual(self.request['ActionAfterCompletion'], 'DELETE')
        self.assertEqual(self.request['FlexibleTimeWindow'], {'Mode': 'OFF'})
        target = self.request['Target']
        self.assertEqual(target['Arn'], 'arn:aws:scheduler:::aws-sdk:sns:publish')
        self.assertEqual(json.loads(target['Input'])['TopicArn'], os.environ['RD_SNS_TOPIC_ARN'])
        self.assertNotIn('notes-only@example.com', target['Input'])
        self.assertFalse(plan['automatic_run'])
        self.sns.publish.assert_not_called()
        self.assertEqual(self.case['review_plan'], plan)

    def test_unconfirmed_subscriber_or_filter_never_creates_a_schedule(self):
        self.sns.list_subscriptions_by_topic.return_value['Subscriptions'][0]['SubscriptionArn'] = 'PendingConfirmation'
        with self.assertRaisesRegex(ValueError, 'No confirmed'):
            self.module.schedule(self.case, self.plan, now=self.now)
        self.scheduler.create_schedule.assert_not_called()
        self.store.update_case.assert_not_called()
        self.sns.list_subscriptions_by_topic.return_value['Subscriptions'][0]['SubscriptionArn'] = 'confirmed'
        self.sns.get_subscription_attributes.return_value = {'Attributes': {'FilterPolicy': '{"type":["other"]}'}}
        with self.assertRaisesRegex(ValueError, 'filter policy'):
            self.module.schedule(self.case, self.plan, now=self.now)
        self.scheduler.create_schedule.assert_not_called()

    def test_timeout_keeps_a_durable_intent_for_cancellation(self):
        self.scheduler.create_schedule.side_effect = TimeoutError('fixture')
        plan = self.module.schedule(self.case, self.plan, now=self.now)
        self.assertEqual(plan['email_delivery'], 'UNCONFIRMED')
        self.assertEqual(plan['reminder']['error'], 'TimeoutError')
        result = self.module.cancel(self.case)
        self.assertEqual(result['email_delivery'], 'CANCELLED')
        self.scheduler.delete_schedule.assert_called_once()

    def test_prior_schedule_is_cancelled_when_its_time_is_replaced(self):
        first = self.module.schedule(self.case, self.plan, now=self.now)
        self.scheduler.reset_mock()
        self.request = None
        changed = {**self.plan, 'review_at_utc': '2026-10-16T17:20:00+00:00'}
        second = self.module.schedule(copy.deepcopy(self.case), changed, now=self.now)
        self.scheduler.delete_schedule.assert_called_once_with(Name=first['reminder']['name'],
            GroupName=first['reminder']['group'])
        self.assertEqual(first['reminder']['name'], second['reminder']['name'])
        self.assertEqual(self.request['ScheduleExpression'], 'at(2026-10-16T17:20:00)')

    def test_namespace_identity_prevents_cancelling_another_workspace(self):
        self.module.schedule(self.case, self.plan, now=self.now)
        with patch.object(self.store, '_NAMESPACE', 'other-workspace'), self.assertRaisesRegex(ValueError, 'identity'):
            self.module.cancel(self.case)
        self.scheduler.delete_schedule.assert_not_called()

    def test_intent_save_failure_and_replay_never_create_a_schedule(self):
        self.store.update_case.side_effect = lambda *a, **kw: None
        with self.assertRaisesRegex(ValueError, 'intent'):
            self.module.schedule(self.case, self.plan, now=self.now)
        self.scheduler.create_schedule.assert_not_called()
        with patch.dict(os.environ, RD_RECORDED_REPLAY='1'), self.assertRaisesRegex(ValueError, 'Recorded'):
            self.module.schedule(self.case, self.plan, now=self.now)

    def test_reminder_requires_a_future_minute_and_matching_role_account(self):
        with self.assertRaisesRegex(ValueError, 'one minute'):
            self.module.schedule(self.case, {**self.plan, 'review_at_utc': '2026-10-16T17:00:30+00:00'}, now=self.now)
        with patch.dict(os.environ, RD_SCHEDULER_ROLE_ARN='arn:aws:iam::999999999999:role/other'), self.assertRaises(ValueError):
            self.module.settings()
        self.scheduler.create_schedule.assert_not_called()


class SetupReminderTests(unittest.TestCase):
    def test_role_is_limited_to_the_exact_topic_and_schedule_group(self):
        from scripts.setup_review_reminders import documents
        topic = 'arn:aws:sns:us-east-1:123456789012:team'
        region, account, trust, policy = documents(topic, 'team-reviews')
        self.assertEqual(policy['Statement'], [{'Effect': 'Allow', 'Action': 'sns:Publish', 'Resource': topic}])
        conditions = trust['Statement'][0]['Condition']['StringEquals']
        self.assertEqual(conditions['aws:SourceAccount'], account)
        self.assertEqual(conditions['aws:SourceArn'], 'arn:aws:scheduler:us-east-1:123456789012:schedule-group/team-reviews')
        self.assertEqual(region, 'us-east-1')

    def test_default_setup_is_a_dry_run(self):
        from scripts.setup_review_reminders import main
        with patch('boto3.Session') as session, contextlib.redirect_stdout(io.StringIO()):
            main(['--topic-arn', 'arn:aws:sns:us-east-1:123456789012:team'])
        session.assert_not_called()
