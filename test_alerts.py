"""
Test script for the free alert system
Run this to verify your alerts are working
"""

from app import create_app
from app.services.alert_service import alert_service

def test_alerts():
    """Test all alert types"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("TESTING CENARIS ALERT SYSTEM")
        print("=" * 60)
        
        if not alert_service.enabled:
            print("\n❌ Alerts are DISABLED")
            print("\nTo enable alerts:")
            print("1. Add to your .env file:")
            print("   ALERTS_ENABLED=true")
            print("   ALERT_EMAILS=your.email@example.com")
            print("\n2. Restart the application")
            print("\n3. Run this test again")
            return
        
        print(f"\n✅ Alerts are ENABLED")
        print(f"📧 Recipients: {', '.join(alert_service.alert_emails)}")
        print(f"\n📨 Sending test alert email...")
        
        alert_service.send_test_alert()
        
        print("\n✅ Test alert sent!")
        print("\n📬 Check your email inbox (may take 1-2 minutes)")
        print("   Subject: [Cenaris Alert] Test Alert - System Working")
        print("\n" + "=" * 60)
        print("ALERT TYPES AVAILABLE:")
        print("=" * 60)
        print("\n1. Critical Errors (Database, Service Failures)")
        print("   - Auto-triggered on critical exceptions")
        print("   - Max 1 alert per 5 minutes")
        print("\n2. Security Breaches (Failed logins, Account lockouts)")
        print("   - Triggered by security events")
        print("   - Max 1 alert per 15 minutes")
        print("\n3. High Error Rate (Multiple errors in short time)")
        print("   - Manual trigger when error threshold exceeded")
        print("   - Max 1 alert per 15 minutes")
        print("\n4. Service Down (Database, Storage, External APIs)")
        print("   - Manual trigger when service unavailable")
        print("   - Max 1 alert per 5 minutes")
        print("\n5. Resource Exhaustion (CPU, Memory, Disk)")
        print("   - Manual trigger based on monitoring")
        print("   - Max 1 alert per 5-15 minutes")
        print("\n" + "=" * 60)

if __name__ == "__main__":
    test_alerts()
