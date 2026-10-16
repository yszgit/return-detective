"""The SQL cache must stay bounded without re-querying recently used results."""
from collections import OrderedDict
import importlib
import unittest
from unittest.mock import patch


class DataCacheTests(unittest.TestCase):
    def test_hot_results_survive_eviction_and_old_results_are_queried_again(self):
        data = importlib.import_module('rd.data')
        with patch.object(data, '_cache', OrderedDict()), patch.object(data, '_CACHE_LIMIT', 2), \
             patch.object(data, 'BACKEND', 'duckdb'), \
             patch.object(data, '_rows_duck', side_effect=lambda sql: [{'query': sql}]) as query:
            data.rows('first')
            data.rows('hot')
            data.rows('first')
            data.rows('third')
            self.assertEqual(list(data._cache), ['first', 'third'])
            self.assertEqual(query.call_count, 3)
            self.assertEqual(data.rows('hot'), [{'query': 'hot'}])
            self.assertEqual(query.call_count, 4)
            self.assertEqual(len(data._cache), 2)
