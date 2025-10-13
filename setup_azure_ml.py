#!/usr/bin/env python3
"""
Setup script for Azure ML integration.
This script helps configure and test the Azure Data Lake connection.
"""

import os
import sys
from dotenv import load_dotenv
from app.services.azure_data_service import azure_data_service

def check_environment():
    """Check if all required environment variables are set."""
    load_dotenv()
    
    print("🔍 Checking Azure ML Configuration...")
    print("=" * 50)
    
    required_vars = [
        'AZURE_STORAGE_CONNECTION_STRING',
        'AZURE_ML_STORAGE_ACCOUNT',
        'AZURE_ML_CONTAINER',
        'AZURE_ML_RESULTS_PATH'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * 20}...{value[-10:]}")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please update your .env file with the required Azure settings.")
        return False
    
    print("\n✅ All environment variables are configured!")
    return True

def test_connection():
    """Test the Azure Data Lake connection."""
    print("\n🔗 Testing Azure Data Lake Connection...")
    print("=" * 50)
    
    try:
        # Test getting compliance files
        files = azure_data_service.get_compliance_files()
        print(f"✅ Successfully connected to Azure Data Lake")
        print(f"📁 Found {len(files)} compliance analysis files")
        
        if files:
            print("\n📋 Available files:")
            for i, file_info in enumerate(files[:5], 1):
                print(f"   {i}. {file_info['file_name']} ({file_info['framework']})")
                print(f"      Last modified: {file_info['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Test getting summary
        summary = azure_data_service.get_dashboard_summary()
        print(f"\n📊 Dashboard Summary:")
        print(f"   Total Files: {summary['total_files']}")
        print(f"   Average Compliance Rate: {summary['avg_compliancy_rate']}%")
        print(f"   Total Requirements: {summary['total_requirements']}")
        print(f"   Complete: {summary['total_complete']}")
        print(f"   Needs Review: {summary['total_needs_review']}")
        print(f"   Missing: {summary['total_missing']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n💡 Troubleshooting tips:")
        print("   1. Check your Azure Storage connection string")
        print("   2. Verify the storage account name and container exist")
        print("   3. Ensure you have proper permissions")
        print("   4. For now, the app will use mock data for demonstration")
        return False

def setup_mock_data():
    """Set up mock data for demonstration."""
    print("\n🎭 Setting up mock data for demonstration...")
    print("=" * 50)
    
    print("✅ Mock data is ready!")
    print("📋 The dashboard will show sample ML analysis results:")
    print("   • SOX Compliance (83.3% compliant)")
    print("   • GDPR Analysis (62.5% compliant)")
    print("   • ISO 27001 (93.3% compliant)")
    print("   • PCI DSS (33.3% compliant)")
    
    print("\n🚀 You can now run your Flask app and see the ML results!")

def main():
    """Main setup function."""
    print("🌟 Azure ML Integration Setup")
    print("=" * 50)
    print("This script will help you configure Azure Data Lake Storage")
    print("integration for your ML compliance analysis results.")
    print()
    
    # Check environment variables
    env_ok = check_environment()
    
    if not env_ok:
        print("\n❌ Environment setup incomplete.")
        print("Please configure your .env file and run this script again.")
        return
    
    # Test Azure connection
    connection_ok = test_connection()
    
    if connection_ok:
        print("\n🎉 Azure ML integration is ready!")
        print("\n🚀 Next steps:")
        print("   1. Start your Flask app: python3 run.py")
        print("   2. Visit the dashboard to see ML results")
        print("   3. Check the 'ML Results' section for detailed analysis")
        print("   4. The dashboard will auto-refresh every 2 minutes")
    else:
        print("\n⚠️  Using mock data for demonstration")
        setup_mock_data()
        print("\n🚀 Next steps:")
        print("   1. Start your Flask app: python3 run.py")
        print("   2. Visit the dashboard to see mock ML results")
        print("   3. Configure real Azure connection later")
    
    print("\n📚 Documentation:")
    print("   • Dashboard: Shows overall ML compliance summary")
    print("   • ML Results: Detailed file-by-file analysis")
    print("   • Gap Analysis: Updated with ML-driven insights")
    print("   • Auto-refresh: Dashboard updates when new files appear")

if __name__ == '__main__':
    main()