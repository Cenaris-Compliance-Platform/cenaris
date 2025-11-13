#!/usr/bin/env python3
"""
Test script to verify ADLS connection and data retrieval
"""
import os
from app.services.azure_data_service import azure_data_service

def test_connection():
    """Test ADLS connection and data retrieval"""
    print("=" * 60)
    print("Testing ADLS Connection")
    print("=" * 60)
    
    # Check connection string
    conn_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if conn_str:
        print("✓ Connection string found")
    else:
        print("✗ Connection string NOT found in environment")
        print("  Please set AZURE_STORAGE_CONNECTION_STRING in .env file")
        return
    
    # Test getting files
    print("\n" + "=" * 60)
    print("Testing File Retrieval (user_1)")
    print("=" * 60)
    
    files = azure_data_service.get_compliance_files(user_id=1)
    print(f"Found {len(files)} files")
    
    for file_info in files:
        print(f"\nFile: {file_info['file_name']}")
        print(f"  Path: {file_info['file_path']}")
        print(f"  Framework: {file_info['framework']}")
        print(f"  Size: {file_info['file_size']} bytes")
    
    # Test reading file content
    if files:
        print("\n" + "=" * 60)
        print("Testing File Content Reading")
        print("=" * 60)
        
        first_file = files[0]
        print(f"Reading: {first_file['file_path']}")
        
        data = azure_data_service.read_adls_file(first_file['file_path'])
        print(f"Rows read: {len(data)}")
        
        if data:
            print("\nSample data:")
            for row in data[:3]:  # Show first 3 rows
                print(f"  {row}")
            
            # Test processing
            print("\n" + "=" * 60)
            print("Testing Data Processing")
            print("=" * 60)
            
            processed = azure_data_service.process_adls_data(data)
            print(f"Total Requirements: {processed['total_requirements']}")
            print(f"Complete: {processed['complete_count']}")
            print(f"Needs Review: {processed['needs_review_count']}")
            print(f"Missing: {processed['missing_count']}")
            print(f"Compliance Rate: {processed['compliancy_rate']}")
            print(f"Overall Status: {processed['overall_status']}")
            
            if processed.get('frameworks'):
                print("\nFramework Details:")
                for fw in processed['frameworks']:
                    print(f"  - {fw['name']}: {fw['score']}/10 ({fw['status']})")
    
    # Test dashboard summary
    print("\n" + "=" * 60)
    print("Testing Dashboard Summary")
    print("=" * 60)
    
    summary = azure_data_service.get_dashboard_summary(user_id=1)
    print(f"Connection Status: {summary['connection_status']}")
    print(f"Total Files: {summary['total_files']}")
    print(f"Avg Compliance Rate: {summary['avg_compliancy_rate']}")
    print(f"Total Requirements: {summary['total_requirements']}")
    print(f"Complete: {summary['total_complete']}")
    print(f"Needs Review: {summary['total_needs_review']}")
    print(f"Missing: {summary['total_missing']}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == '__main__':
    test_connection()
