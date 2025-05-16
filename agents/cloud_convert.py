import os
import sys
import time
import traceback
import requests
from pathlib import Path

# Add the parent directory to sys.path when running as a script
if __name__ == "__main__":
    # Get the directory containing this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the parent directory (project root)
    parent_dir = os.path.dirname(current_dir)
    # Add to path if not already there
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

sys.path.append('..')

class CloudConvertClient:
    """
    Client for CloudConvert API to convert files between formats.
    """
    
    def __init__(self, api_key):
        """
        Initialize the CloudConvert client.
        
        Args:
            api_key (str): CloudConvert API key
        """
        self.api_key = api_key
        self.base_url = "https://api.cloudconvert.com/v2"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def convert_markdown_to_docx(self, input_file_path):
        """
        Convert markdown file to DOCX format using CloudConvert.
        
        Args:
            input_file_path (str): Path to the input markdown file
            
        Returns:
            str: Path to the converted DOCX file
        """
        print("[CLOUDCONVERT] Starting conversion of markdown to DOCX...")
        
        # Validate input file
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"Input file not found: {input_file_path}")
        
        # Create output file path (same name with .docx extension)
        input_path = Path(input_file_path)
        output_file_path = str(input_path.with_suffix('.docx'))
        
        # Create conversion job
        job_data = self._create_conversion_job(input_file_path)
        
        if not job_data:
            raise Exception("Failed to create conversion job")
        
        # Get the upload URL from the import task
        upload_task = next((task for task in job_data.get('tasks', []) if task.get('name') == 'import-my-file'), None)
        if not upload_task or 'result' not in upload_task or 'form' not in upload_task['result']:
            raise Exception("Failed to get upload URL")
        
        upload_url = upload_task['result']['form']['url']
        upload_params = upload_task['result']['form']['parameters']
        
        # Upload the file
        with open(input_file_path, 'rb') as file:
            files = {'file': file}
            response = requests.post(upload_url, data=upload_params, files=files)
            
        if response.status_code != 201 and response.status_code != 200:
            raise Exception(f"Failed to upload file: {response.text}")
        
        # Wait for job completion
        job_id = job_data['id']
        completed_job = self._wait_for_job_completion(job_id)
        
        if not completed_job:
            raise Exception("Job did not complete successfully")
        
        # Get the download URL
        export_task = next((task for task in completed_job.get('tasks', []) if task.get('name') == 'export-my-file'), None)
        if not export_task or 'result' not in export_task or 'files' not in export_task['result']:
            raise Exception("Failed to get download URL")
        
        download_url = export_task['result']['files'][0]['url']
        
        # Download the file
        self._download_result(download_url, output_file_path)
        
        print(f"[CLOUDCONVERT] Conversion complete: {output_file_path}")
        return output_file_path
    
    def _create_conversion_job(self, input_file_path):
        """
        Create a conversion job for markdown to DOCX.
        
        Args:
            input_file_path (str): Path to the input markdown file
            
        Returns:
            dict: Job data
        """
        # Prepare job payload
        job_payload = {
            "tasks": {
                "import-my-file": {
                    "operation": "import/upload"
                },
                "convert-my-file": {
                    "operation": "convert",
                    "input": "import-my-file",
                    "output_format": "docx",
                    "engine": "pandoc"
                },
                "export-my-file": {
                    "operation": "export/url",
                    "input": "convert-my-file"
                }
            }
        }
        
        # Create job
        response = requests.post(
            f"{self.base_url}/jobs",
            headers=self.headers,
            json=job_payload
        )
        
        if response.status_code != 201:
            print(f"[CLOUDCONVERT] Error creating job: {response.text}")
            return None
        
        return response.json()['data']
    
    def _wait_for_job_completion(self, job_id, max_wait_time=300, check_interval=2):
        """
        Wait for job completion with timeout.
        
        Args:
            job_id (str): ID of the job to wait for
            max_wait_time (int): Maximum wait time in seconds
            check_interval (int): Interval between status checks in seconds
            
        Returns:
            dict: Completed job data or None if timeout
        """
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            # Get job status
            response = requests.get(
                f"{self.base_url}/jobs/{job_id}",
                headers=self.headers
            )
            
            if response.status_code != 200:
                print(f"[CLOUDCONVERT] Error checking job status: {response.text}")
                return None
            
            job_data = response.json()['data']
            status = job_data['status']
            
            if status == 'finished':
                return job_data
            elif status in ['error', 'canceled']:
                print(f"[CLOUDCONVERT] Job failed with status: {status}")
                return None
            
            # Wait before checking again
            time.sleep(check_interval)
        
        print(f"[CLOUDCONVERT] Timeout waiting for job completion")
        return None
    
    def _download_result(self, download_url, output_path):
        """
        Download the result file from URL.
        
        Args:
            download_url (str): URL to download the file from
            output_path (str): Path to save the downloaded file
            
        Returns:
            bool: True if successful, False otherwise
        """
        response = requests.get(download_url, stream=True)
        if response.status_code != 200:
            raise Exception(f"Failed to download file: {response.text}")
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True


# Test function to verify the CloudConvert client works
if __name__ == "__main__":
    try:
        from config import CLOUDCONVERT_API_KEY
        
        # Check if API key is available
        if not CLOUDCONVERT_API_KEY:
            print("Error: CLOUDCONVERT_API_KEY not found in environment variables.")
            sys.exit(1)
        
        # Check if a test file path is provided
        if len(sys.argv) < 2:
            print("Usage: python cloud_convert.py <path_to_markdown_file>")
            sys.exit(1)
        
        input_file = sys.argv[1]
        if not os.path.exists(input_file):
            print(f"Error: Input file not found: {input_file}")
            sys.exit(1)
        
        # Create client and convert file
        client = CloudConvertClient(CLOUDCONVERT_API_KEY)
        output_file = client.convert_markdown_to_docx(input_file)
        
        print(f"Test successful! Converted file: {output_file}")
        
    except Exception as e:
        print(f"Error in test: {e}")
        traceback.print_exc()
        sys.exit(1) 