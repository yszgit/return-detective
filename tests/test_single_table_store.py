"""PK/SK storage round trips, pagination and namespace-scoped reset without AWS."""
from decimal import Decimal
import unittest
from unittest.mock import patch, Mock

from rd import store


class Table:
    def __init__(self):
        self.items = {}

    def query(self, KeyConditionExpression, **kwargs):
        partition, prefix = KeyConditionExpression.get_expression()['values']
        pk = partition.get_expression()['values'][1]
        sk = prefix.get_expression()['values'][1]
        return {'Items': [v for (p, s), v in self.items.items()
                          if p == pk and s.startswith(sk)]}

    def batch_writer(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def put_item(self, Item):
        self.items[(Item['PK'], Item['SK'])] = Item

    def delete_item(self, Key):
        self.items.pop((Key['PK'], Key['SK']), None)


class SingleTableTests(unittest.TestCase):
    def setUp(self):
        # Another test replaces boto3 modules temporarily, so always import the
        # real condition class after that patch is released.
        from boto3.dynamodb import conditions
        self.assertTrue(hasattr(conditions, 'Key'))
        self.table = Table()
        self.resource = Mock()
        self.resource.Table.return_value = self.table
        self.patches = patch.multiple(store, STORE_BACKEND='dynamodb',
            STATE_TABLE='return-detective-state', _NAMESPACE='team-a', _DDB=self.resource)
        self.patches.start()
        self.addCleanup(self.patches.stop)

    def test_round_trip_repeated_approval_and_reset_isolation(self):
        self.table.items[('RUN#other', 'CASE#other')] = {
            'PK': 'RUN#other', 'SK': 'CASE#other', 'case_id': 'other'}
        c = store.open_case('Glindafied', 'Quality', '2024-11-23', 'summary', 'evidence')
        cid = c['case_id']
        store.link_returns(cid, [243470])
        store.update_case(cid, confidence='High')
        store.log_action(cid, 1, 'Notify', {'amount': 2.5})
        a = store.request_approval(cid, 4, 'Hold stock', {}, 'Quality')
        store.decide_approval(a['approval_id'], True)
        self.assertIsNone(store.decide_approval(a['approval_id'], True))
        result = store.snapshot()
        self.assertEqual(result['cases'][cid]['linked_return_ids'], [243470])
        self.assertEqual(result['approvals'][0]['status'], 'APPROVED')
        self.assertEqual(len(result['actions']), 2)
        self.assertNotIn('PK', result['cases'][cid])
        self.assertTrue(all(call.args == ('return-detective-state',)
                            for call in self.resource.Table.call_args_list))
        # A new client reads persisted records; state is not a local cache.
        resource = Mock()
        resource.Table.return_value = self.table
        with patch.object(store, '_DDB', resource):
            self.assertEqual(store.get_case(cid)['confidence'], 'High')
        store.reset()
        self.assertEqual(store.snapshot(), {'cases': {}, 'actions': [], 'approvals': []})
        self.assertEqual(list(self.table.items), [('RUN#other', 'CASE#other')])

    def test_pagination_and_decimal_conversion(self):
        table = Mock()
        table.query.side_effect = [
            {'Items': [{'PK': 'RUN#team-a', 'SK': 'ACTION#a', 'action_id': 'a',
                        'detail': {'amount': Decimal('1.25')}}],
             'LastEvaluatedKey': {'PK': 'RUN#team-a', 'SK': 'ACTION#a'}},
            {'Items': [{'PK': 'RUN#team-a', 'SK': 'ACTION#b', 'action_id': 'b'}]}]
        self.resource.Table.return_value = table
        result = store._records('actions')
        self.assertEqual([r['action_id'] for r in result], ['a', 'b'])
        self.assertEqual(result[0]['detail']['amount'], 1.25)
        self.assertIn('ExclusiveStartKey', table.query.call_args.kwargs)
        self.assertTrue(table.query.call_args.kwargs['ConsistentRead'])
