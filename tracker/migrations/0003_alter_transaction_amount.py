import decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0002_category_name_unique_transaction_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='amount',
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[MinValueValidator(decimal.Decimal('0.01'))],
            ),
        ),
    ]
