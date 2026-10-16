import contextlib
import importlib
import io
import os
import unittest
from unittest.mock import patch


class AwsCheckTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('scripts.check_aws')

    def test_default_checks_never_call_a_model(self):
        with patch.dict(os.environ, AWS_REGION='us-east-1'), \
             patch.object(self.module, 'check_identity'), patch.object(self.module, 'check_athena') as data, \
             patch.object(self.module, 'check_model') as model, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.main([]), 0)
        data.assert_called_once()
        model.assert_not_called()

    def test_model_only_skips_data_and_requires_an_explicit_model(self):
        with patch.dict(os.environ, AWS_REGION='us-east-1', RD_MODEL_ID='fixture-model'), \
             patch.object(self.module, 'check_identity'), patch.object(self.module, 'check_athena') as data, \
             patch.object(self.module, 'check_model') as model, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.main(['--model-only']), 0)
        data.assert_not_called()
        model.assert_called_once()
        with patch.dict(os.environ, AWS_REGION='us-east-1', RD_MODEL_ID=''), \
             patch.object(self.module, 'check_identity') as identity, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.main(['--model-only']), 1)
        identity.assert_not_called()
