#!/usr/bin/env python3
"""Simple ADLS debug script"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 60)
print("ADLS Connection Debug")
print("=" * 60)

# Check connection string
conn_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
if conn_str:
    print("✓ Connection string found")
    print(f"  Account: {conn_str.split('AccountName=')[1].split(';')[0] if 'AccountName=' in conn_str else 'Unknown'}")
else:
    print("✗ Connection string NOT found")
    exit(1)

# Try to connect
try:
    from azure.storage.filedatalake import DataLakeServiceClient
    print("✓ Azure SDK imported successfully")
    
    service_client = DataLakeServiceClient.from_connection_string(conn_str)
    print("✓ Service client created")
    
    # Try to list containers
    print("\n" + "=" * 60)
    print("Listing Containers")
    print("=" * 60)
    
    file_systems = service_client.list_file_systems()
    for fs in file_systems:
        print(f"  - {fs.name}")
    
    # Try to access 'results' container
    print("\n" + "=" * 60)
    print("Accessing 'results' container")
    print("=" * 60)
    
    container_client = service_client.get_file_system_client("results")
    
    # List paths in compliance-results
    print("\nListing files in: compliance-results/2025/11/user_1/")
    paths = container_client.get_paths(path="compliance-results/2025/11/user_1")
    
    file_count = 0
    for path in paths:
        if not path.is_directory:
            print(f"  ✓ Found: {path.name}")
            print(f"    Size: {path.content_length} bytes")
            print(f"    Modified: {path.last_modified}")
            file_count += 1
    
    if file_count == 0:
        print("  ✗ No files found in this path")
        print("\n  Trying broader search: compliance-results/")
        paths = container_client.get_paths(path="compliance-results")
        for path in paths:
            print(f"    {path.name} {'(dir)' if path.is_directory else ''}")
    
except ImportError as e:
    print(f"✗ Azure SDK not installed: {e}")
    print("  Run: pip install azure-storage-file-datalake")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
