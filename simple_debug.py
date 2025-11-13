#!/usr/bin/env python3
"""Minimal ADLS debug"""
import os

print("Checking .env file...")
with open('.env', 'r') as f:
    for line in f:
        if 'AZURE_STORAGE_CONNECTION_STRING' in line:
            print(f"Found: {line[:80]}...")
            if 'AccountName=' in line:
                account = line.split('AccountName=')[1].split(';')[0]
                print(f"Account Name: {account}")

print("\nTrying Azure connection...")
try:
    from azure.storage.filedatalake import DataLakeServiceClient
    
    # Read connection string from .env
    conn_str = None
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('AZURE_STORAGE_CONNECTION_STRING='):
                conn_str = line.split('=', 1)[1].strip()
                break
    
    if not conn_str:
        print("ERROR: No connection string found")
        exit(1)
    
    print("Creating service client...")
    service_client = DataLakeServiceClient.from_connection_string(conn_str)
    
    print("Listing containers...")
    for fs in service_client.list_file_systems():
        print(f"  Container: {fs.name}")
    
    print("\nTrying to access 'results' container...")
    container = service_client.get_file_system_client("results")
    
    print("Listing all paths in compliance-results/...")
    paths = list(container.get_paths(path="compliance-results"))
    
    if not paths:
        print("  No paths found!")
    else:
        for p in paths[:20]:  # Show first 20
            print(f"  {p.name} {'[DIR]' if p.is_directory else f'[{p.content_length} bytes]'}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
