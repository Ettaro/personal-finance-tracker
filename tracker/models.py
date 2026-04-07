from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('receita', 'Receita'),
        ('despesa', 'Despesa'),
    )

    type = models.CharField(max_length=7, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    date = models.DateField(default=timezone.localdate)

    def __str__(self):
        return f"{self.description} - {self.amount}"
