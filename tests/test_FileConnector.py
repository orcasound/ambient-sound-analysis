import datetime as dt
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

# Mock boto3 and botocore before importing file_connector
with patch.dict(sys.modules, {
    'boto3': MagicMock(),
    'botocore': MagicMock(),
    'botocore.config': MagicMock(),
    'botocore.exceptions': MagicMock(),
}):
    # Set up the Config class and UNSIGNED constant on the mocked modules
    sys.modules['botocore.config'].Config = MagicMock()
    sys.modules['botocore'].UNSIGNED = 'aws:unsigned'
    sys.modules['botocore.exceptions'].ClientError = Exception
    
    from orcasound_noise.utils.file_connector import S3FileConnector

def test_create_filename():
    filename = S3FileConnector.create_filename(
        dt.datetime(2023, 1, 1, 6, 30),
        dt.datetime(2023, 1, 1, 12, 30),
        60,
        100
    )

    assert filename == "20230101T063000_20230101T123000_60s_100hz.parquet"

def test_parse_filename():
    filename = "20230101T063000_20230101T123000_60s_100hz.parquet"

    assert S3FileConnector.parse_filename(filename) == [
        dt.datetime(2023, 1, 1, 6, 30),
        dt.datetime(2023, 1, 1, 12, 30),
        60,
        100,
        "delta_hz"
    ]


class TestUploadPartitionedFolder:
    """Test suite for upload_partitioned_folder method"""
    
    @pytest.fixture
    def mock_hydrophone(self):
        """Create a mock hydrophone for testing"""
        mock_hp = MagicMock()
        mock_hp.value.bucket = 'test-source-bucket'
        mock_hp.value.ref_folder = 'ref-folder'
        mock_hp.value.save_bucket = 'test-archive-bucket'
        mock_hp.value.save_folder = 'archive/psd'
        return mock_hp
    
    @patch('orcasound_noise.utils.file_connector.boto3.resource')
    @patch('orcasound_noise.utils.file_connector.boto3.client')
    def test_upload_partitioned_folder_valid_path(self, mock_boto_client, mock_boto_resource, mock_hydrophone):
        """Test successful upload with valid folder path containing save_folder"""
        with patch('subprocess.run') as mock_subprocess:
            connector = S3FileConnector(mock_hydrophone)
            folder_path = '/local/path/archive/psd/year=2023/month=01'
            
            connector.upload_partitioned_folder(folder_path)
            
            # Verify subprocess.run was called with correct arguments
            expected_cmd = [
                'aws', 's3', 'sync',
                folder_path,
                's3://test-archive-bucket/archive/psd/',
                '--no-overwrite'
            ]
            mock_subprocess.assert_called_once_with(expected_cmd, check=True, capture_output=True, text=True)
    
    @patch('orcasound_noise.utils.file_connector.boto3.resource')
    @patch('orcasound_noise.utils.file_connector.boto3.client')
    def test_upload_partitioned_folder_validates_path(self, mock_boto_client, mock_boto_resource, mock_hydrophone):
        """Test that ValueError is raised when folder_path doesn't contain save_folder"""
        with patch('subprocess.run') as mock_subprocess:
            connector = S3FileConnector(mock_hydrophone)
            invalid_folder_path = '/local/path/wrong/folder/year=2023'
            
            with pytest.raises(ValueError, match="folder_path must include 'archive/psd'"):
                connector.upload_partitioned_folder(invalid_folder_path)
            
            # subprocess.run should not be called
            mock_subprocess.assert_not_called()
    
    @patch('orcasound_noise.utils.file_connector.boto3.resource')
    @patch('orcasound_noise.utils.file_connector.boto3.client')
    def test_upload_partitioned_folder_subprocess_failure(self, mock_boto_client, mock_boto_resource, mock_hydrophone):
        """Test that subprocess failures are propagated"""
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.side_effect = RuntimeError("AWS CLI not found")
            
            connector = S3FileConnector(mock_hydrophone)
            folder_path = '/local/path/archive/psd/year=2023'
            
            with pytest.raises(RuntimeError, match="AWS CLI not found"):
                connector.upload_partitioned_folder(folder_path)
    
    @patch('orcasound_noise.utils.file_connector.boto3.resource')
    @patch('orcasound_noise.utils.file_connector.boto3.client')
    def test_upload_partitioned_folder_with_multiple_levels(self, mock_boto_client, mock_boto_resource, mock_hydrophone):
        """Test upload with deeply nested folder structure"""
        with patch('subprocess.run') as mock_subprocess:
            connector = S3FileConnector(mock_hydrophone)
            folder_path = '/data/archive/psd/hydrophone=orca_lab/year=2026/month=02/day=05'
            
            connector.upload_partitioned_folder(folder_path)
            
            expected_cmd = [
                'aws', 's3', 'sync',
                folder_path,
                's3://test-archive-bucket/archive/psd/',
                '--no-overwrite'
            ]
            mock_subprocess.assert_called_once_with(expected_cmd, check=True, capture_output=True, text=True)
    
    @patch('orcasound_noise.utils.file_connector.boto3.resource')
    @patch('orcasound_noise.utils.file_connector.boto3.client')
    def test_upload_partitioned_folder_case_sensitive(self, mock_boto_client, mock_boto_resource, mock_hydrophone):
        """Test that save_folder matching is case sensitive"""
        with patch('subprocess.run') as mock_subprocess:
            connector = S3FileConnector(mock_hydrophone)
            # Using uppercase version of save_folder should fail
            invalid_folder_path = '/local/path/ARCHIVE/PSD/year=2023'
            
            with pytest.raises(ValueError, match="folder_path must include 'archive/psd'"):
                connector.upload_partitioned_folder(invalid_folder_path)
            
            mock_subprocess.assert_not_called()
    
    @patch('orcasound_noise.utils.file_connector.boto3.resource')
    @patch('orcasound_noise.utils.file_connector.boto3.client')
    def test_upload_partitioned_folder_with_check_exception(self, mock_boto_client, mock_boto_resource, mock_hydrophone):
        """Test that CalledProcessError is raised when subprocess check=True fails"""
        import subprocess
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'aws s3 sync')
            
            connector = S3FileConnector(mock_hydrophone)
            folder_path = '/local/path/archive/psd/year=2023'
            
            with pytest.raises(subprocess.CalledProcessError):
                connector.upload_partitioned_folder(folder_path)
    
    @patch('orcasound_noise.utils.file_connector.boto3.resource')
    @patch('orcasound_noise.utils.file_connector.boto3.client')
    def test_upload_partitioned_folder_minimal_path(self, mock_boto_client, mock_boto_resource, mock_hydrophone):
        """Test with minimal valid path (just save_folder)"""
        with patch('subprocess.run') as mock_subprocess:
            connector = S3FileConnector(mock_hydrophone)
            # Minimal valid path
            folder_path = 'archive/psd'
            
            connector.upload_partitioned_folder(folder_path)
            
            expected_cmd = [
                'aws', 's3', 'sync',
                folder_path,
                's3://test-archive-bucket/archive/psd/',
                '--no-overwrite'
            ]
            mock_subprocess.assert_called_once_with(expected_cmd, check=True, capture_output=True, text=True)