#!/usr/bin/env python3
"""Check what containers exist in your Azure storage"""
import os
from dotenv import load_dotenv

load_dotenv()

try:
    from azure.storage.filedatalake import DataLakeServiceClient
    
    conn_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if not conn_str:
        print("❌ No connection string found!")
        exit(1)
    
    print("Connecting to Azure...")
    service_client = DataLakeServiceClient.from_connection_string(conn_str)
    
    print("\n" + "="*60)
    print("CONTAINERS IN YOUR STORAGE ACCOUNT:")
    print("="*60)
    
    file_systems = service_client.list_file_systems()
    containers = []
    
    for fs in file_systems:
        containers.append(fs.name)
        print(f"  ✓ {fs.name}")
    
    print("\n" + "="*60)
    print(f"Total containers found: {len(containers)}")
    print("="*60)
    
    print("\nYour .env file says:")
    print(f"  AZURE_ML_CONTAINER={os.getenv('AZURE_ML_CONTAINER')}")
    
    ml_container = os.getenv('AZURE_ML_CONTAINER')
    if ml_container in containers:
        print(f"  ✓ Container '{ml_container}' EXISTS!")
    else:
        print(f"  ❌ Container '{ml_container}' DOES NOT EXIST!")
        print(f"\n  Available containers: {', '.join(containers)}")
        print(f"\n  Update your .env file to use one of these containers!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
