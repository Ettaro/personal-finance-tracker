from django.conf import settings
from django.db import migrations


DEFAULT_CATEGORIES = (
    'Food',
    'Transport',
    'Leisure',
    'Salary',
    'Health',
    'Subscriptions',
    'Housing',
    'Education',
    'Shopping',
    'Other',
)


def create_default_categories(apps, schema_editor):
    user_app_label, user_model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(user_app_label, user_model_name)
    Category = apps.get_model('tracker', 'Category')

    for user in User.objects.all():
        for category_name in DEFAULT_CATEGORIES:
            Category.objects.get_or_create(user=user, name=category_name)


def remove_default_categories(apps, schema_editor):
    Category = apps.get_model('tracker', 'Category')
    Category.objects.filter(name__in=DEFAULT_CATEGORIES).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tracker', '0005_alter_transaction_type'),
    ]

    operations = [
        migrations.RunPython(create_default_categories, remove_default_categories),
    ]
