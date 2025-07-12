from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid
from accounts.models import User
# User = get_user_model()

def generate_tx_id():
    return str(uuid.uuid4())

class Transaction(models.Model):
    class Type(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposit'
        PAYMENT = 'payment', 'Payment'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey("Wallet", on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=10, choices=Type.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    description = models.CharField(max_length=255, blank=True)
    tx_hash = models.CharField(max_length=255, blank=True, db_index=True)
    tx_id = models.CharField(max_length=36, unique=True, default=generate_tx_id)
    address = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'status']),
        ]

    def __str__(self):
        return f"{self.type.title()} ${abs(self.amount)} ({self.status})"



class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.user.username}'s Wallet"

    @transaction.atomic
    def credit(self, amount: Decimal):
        amount = Decimal(amount)
        if amount <= 0:
            raise ValueError("Credit amount must be positive")

        self.balance += amount
        self.save(update_fields=['balance'])

    @transaction.atomic
    def debit(self, amount: Decimal, *, description=''):
        print("isHere")
        amount = Decimal(amount)
        if amount <= 0:
            raise ValueError("Debit amount must be positive")

        if self.balance < amount:
            raise ValidationError("Insufficient wallet balance")

        self.balance -= amount
        self.save(update_fields=['balance'])

        return Transaction.objects.create(
            wallet=self,
            type=Transaction.Type.PAYMENT,
            amount=-amount,
            status=Transaction.Status.COMPLETED,
            description=description
        )
