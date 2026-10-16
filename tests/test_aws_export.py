"""An upload must stop before writing if the bucket is not owned by this account."""
import argparse
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import export_aws_dataset


class AwsExportTests(unittest.TestCase):
    def test_owner_check_precedes_every_upload(self):
        session = Mock()
        session.client.return_value.get_caller_identity.return_value = {'Account': '123456789012'}
        s3 = Mock()
        s3.head_bucket.side_effect = PermissionError('wrong bucket owner')
        session.client.side_effect = lambda name: s3 if name == 's3' else Mock(
            get_caller_identity=Mock(return_value={'Account': '123456789012'}))
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(export_aws_dataset, 'validate', return_value=({}, {})), \
             patch.object(export_aws_dataset, 'make_ddl', return_value='-- fixture'), \
             patch.object(export_aws_dataset, 'upload_plan', return_value=[(Path(folder) / 'file', 'key')]), \
             patch('boto3.Session', return_value=session), contextlib.redirect_stdout(io.StringIO()):
            args = argparse.Namespace(data_dir=folder, bucket='fixture-bucket', prefix='curated/test',
                                      database='fixture_db', ddl_out=Path(folder) / 'ddl.sql', execute=True)
            with self.assertRaises(PermissionError):
                export_aws_dataset.main(args)
        s3.head_bucket.assert_called_once_with(Bucket='fixture-bucket', ExpectedBucketOwner='123456789012')
        s3.upload_file.assert_not_called()
