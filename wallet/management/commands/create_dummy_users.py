"""
Django management command to create dummy test users
Usage: python manage.py create_dummy_users
"""

from django.core.management.base import BaseCommand
from accounts.models import User
from wallet.models import Wallet
from decimal import Decimal
import random

class Command(BaseCommand):
    help = 'Create 3 dummy test users with wallets and transactions'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creating dummy test users...')
        
        # Dummy user data
        users_data = [
            {
                'username': 'john_doe',
                'email': 'john.doe@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'balance': Decimal('2450.75'),
            },
            {
                'username': 'sarah_smith',
                'email': 'sarah.smith@example.com',
                'first_name': 'Sarah',
                'last_name': 'Smith',
                'balance': Decimal('5890.00'),
            },
            {
                'username': 'mike_johnson',
                'email': 'mike.johnson@example.com',
                'first_name': 'Mike',
                'last_name': 'Johnson',
                'balance': Decimal('1234.50'),
            },
        ]
        
        for user_data in users_data:
            # Create user if doesn't exist
            user, created = User.objects.get_or_create(
                email=user_data['email'],
                defaults={
                    'username': user_data['username'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'is_active': True,
                }
            )
            
            if created:
                user.set_unusable_password()  # No password needed for testing
                user.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Created user: {user.email}'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ User already exists: {user.email}'))
            
            # Create wallet with balance
            wallet, _ = Wallet.objects.get_or_create(
                user=user,
                defaults={'balance': user_data['balance']}
            )
            
            self.stdout.write(f'  Wallet balance: ${wallet.balance}')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Done! Created 3 test users with wallets.'))
        self.stdout.write(self.style.SUCCESS('\nTest Users:'))
        self.stdout.write('  1. john.doe@example.com (John Doe) - $2,450.75')
        self.stdout.write('  2. sarah.smith@example.com (Sarah Smith) - $5,890.00')
        self.stdout.write('  3. mike.johnson@example.com (Mike Johnson) - $1,234.50')
