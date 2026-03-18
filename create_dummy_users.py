#!/usr/bin/env python
"""
Create 3 dummy users with realistic names and emails for testing.
Run with: python manage.py shell < create_dummy_users.py
"""

from accounts.models import User
from wallet.models import Wallet
from decimal import Decimal

# Create 3 dummy users with realistic names (using username to store display name)
dummy_users = [
    {
        "username": "sarah.smith",
        "email": "sarah.smith@example.com",
        "balance": 5890.00,
    },
    {
        "username": "mike.johnson",
        "email": "mike.johnson@example.com",
        "balance": 1234.50,
    },
    {
        "username": "emma.wilson",
        "email": "emma.wilson@example.com",
        "balance": 3567.89,
    },
]

created_count = 0
for user_data in dummy_users:
    user, created = User.objects.get_or_create(
        email=user_data["email"],
        defaults={
            "username": user_data["username"],
            "is_active": True,
        }
    )
    
    if created:
        # Set a default password
        user.set_password("password123")
        user.save()
        print(f"✅ Created user: {user.username} ({user.email})")
        
        # Create wallet with initial balance
        wallet, _ = Wallet.objects.get_or_create(
            user=user,
            defaults={"balance": Decimal(str(user_data["balance"]))}
        )
        print(f"   💰 Wallet created with balance: ${wallet.balance}")
        created_count += 1
    else:
        print(f"⚠️  User already exists: {user.username} ({user.email})")
        # Ensure wallet exists for this user
        wallet, wallet_created = Wallet.objects.get_or_create(
            user=user,
            defaults={"balance": Decimal(str(user_data["balance"]))}
        )
        if wallet_created:
            print(f"   💰 Wallet created with balance: ${wallet.balance}")
        else:
            print(f"   💰 Existing wallet balance: ${wallet.balance}")

print(f"\n🎉 Done! Created {created_count} new users.")
print("\n📋 Login credentials for all users:")
print("   Email: [user email from above]")
print("   Password: password123")
