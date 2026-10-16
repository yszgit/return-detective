"""SNS integration checks use mocked clients and never send email."""
import importlib
import os
import unittest
from unittest.mock import MagicMock, patch


class NotificationsTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('rd.notifications')
        self.case = dict(case_id='CASE-TEST', style='Test shoe', category='Quality',
                         opened_as_of='2024-11-23', owner_team='Quality', confidence='Medium')
        self.store = MagicMock()
        self.store.get_case.side_effect = lambda cid: self.case.copy()
        self.store.snapshot.return_value = {'approvals': [dict(case_id='CASE-TEST',
            status='PENDING', action='Hold stock') ]}
        self.store.update_case.side_effect = lambda cid, **fields: self.case.update(fields)
        self.store_patch = patch.object(self.module, 'store', self.store)
        self.store_patch.start()
        self.addCleanup(self.store_patch.stop)
        env = patch.dict(os.environ, {'RD_SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test',
                                     'RD_RECORDED_REPLAY': '0'})
        env.start()
        self.addCleanup(env.stop)
        self.client_patch = patch('boto3.client')
        self.factory = self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.client = self.factory.return_value
        self.client.publish.return_value = {'MessageId': 'message-123'}

    def test_success_saved_and_repeat_does_not_publish_again(self):
        first = self.module.notify_case('CASE-TEST')
        self.assertEqual(first['status'], 'ACCEPTED')
        self.assertEqual(first['message_id'], 'message-123')
        self.assertEqual(self.module.notify_case('CASE-TEST'), first)
        self.client.publish.assert_called_once()
        payload = self.client.publish.call_args.kwargs
        self.assertIn('2024-11-23', payload['Message'])
        self.assertIn('Hold stock', payload['Message'])

    def test_scripted_and_recorded_never_send(self):
        self.assertEqual(self.module.notify_case('CASE-TEST', scripted=True)['status'], 'SIMULATED')
        with patch.dict(os.environ, RD_RECORDED_REPLAY='1'):
            self.module.notify_case('CASE-TEST')
        self.factory.assert_not_called()
        self.store.update_case.assert_not_called()

    def test_missing_topic_can_be_retried_after_configuration(self):
        with patch.dict(os.environ, RD_SNS_TOPIC_ARN=''):
            self.assertEqual(self.module.notify_case('CASE-TEST')['status'], 'NOT_CONFIGURED')
        self.factory.assert_not_called()
        self.assertEqual(self.module.notify_case('CASE-TEST', retry=True)['status'], 'ACCEPTED')

    def test_publish_failure_preserves_case_and_requires_explicit_retry(self):
        self.client.publish.side_effect = TimeoutError('timed out')
        self.assertEqual(self.module.notify_case('CASE-TEST')['status'], 'UNCONFIRMED')
        self.assertEqual(self.case['case_id'], 'CASE-TEST')
        self.module.notify_case('CASE-TEST')
        self.client.publish.assert_called_once()
        self.client.publish.side_effect = None
        self.module.notify_case('CASE-TEST', retry=True)
        self.assertEqual(self.client.publish.call_count, 2)

    def test_missing_case_never_sends(self):
        self.store.get_case.side_effect = lambda cid: None
        with self.assertRaises(ValueError):
            self.module.notify_case('missing')
        self.factory.assert_not_called()

    def test_inflight_publish_not_repeated(self):
        self.case['case_notification'] = {'status': 'PUBLISHING'}
        self.module.notify_case('CASE-TEST', retry=True)
        self.factory.assert_not_called()

    def test_fifo_topic_rejected(self):
        with patch.dict(os.environ, RD_SNS_TOPIC_ARN='arn:aws:sns:us-east-1:123456789012:test.fifo'):
            self.assertEqual(self.module.notify_case('CASE-TEST')['status'], 'NOT_CONFIGURED')
        self.factory.assert_not_called()
