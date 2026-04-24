from django.conf import settings
from django.db import migrations, models


def assign_existing_data_to_first_user(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    Category = apps.get_model('tracker', 'Category')
    Transaction = apps.get_model('tracker', 'Transaction')

    first_user = User.objects.order_by('id').first()
    if not first_user:
        return

    Category.objects.filter(user__isnull=True).update(user=first_user)
    Transaction.objects.filter(user__isnull=True).update(user=first_user)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tracker', '0003_alter_transaction_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='transaction',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='category',
            name='name',
            field=models.CharField(max_length=100),
        ),
        migrations.RunPython(assign_existing_data_to_first_user, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(fields=('user', 'name'), name='unique_category_name_per_user'),
        ),
    ]
