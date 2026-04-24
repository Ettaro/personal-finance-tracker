from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Transaction


class TrackerViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='tester',
            password='safe-password-123',
        )
        self.other_user = get_user_model().objects.create_user(
            username='someone-else',
            password='other-password-123',
        )
        self.client.login(username='tester', password='safe-password-123')
        self.category = Category.objects.create(user=self.user, name='Housing')

    def test_create_transaction_with_valid_data(self):
        response = self.client.post(
            reverse('list_transactions'),
            {
                'type': 'despesa',
                'amount': '1200.50',
                'category': self.category.id,
                'description': 'Rent',
                'date': '2026-03-26',
            },
        )

        self.assertRedirects(response, reverse('list_transactions'))
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.amount, Decimal('1200.50'))
        self.assertEqual(transaction.date.isoformat(), '2026-03-26')

    def test_create_transaction_rejects_non_positive_amount(self):
        response = self.client.post(
            reverse('list_transactions'),
            {
                'type': 'despesa',
                'amount': '0',
                'category': self.category.id,
                'description': 'Invalid bill',
                'date': '2026-03-26',
            },
            follow=True,
        )

        self.assertContains(response, 'Transaction amount must be greater than zero.')
        self.assertEqual(Transaction.objects.count(), 0)

    def test_create_transaction_rejects_amount_above_model_limit(self):
        response = self.client.post(
            reverse('list_transactions'),
            {
                'type': 'receita',
                'amount': '999999999999999999999999',
                'category': self.category.id,
                'description': 'Huge amount',
                'date': '2026-03-26',
            },
            follow=True,
        )

        self.assertContains(response, 'The amount exceeds the supported limit.')
        self.assertEqual(Transaction.objects.count(), 0)

    def test_create_transaction_requires_existing_category(self):
        response = self.client.post(
            reverse('list_transactions'),
            {
                'type': 'despesa',
                'amount': '12.00',
                'category': 9999,
                'description': 'Test',
                'date': '2026-03-26',
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_create_category_rejects_duplicate_name_case_insensitive(self):
        response = self.client.post(
            reverse('list_categories'),
            {'name': 'housing'},
            follow=True,
        )

        self.assertContains(response, 'A category with this name already exists.')
        self.assertEqual(Category.objects.count(), 1)

    def test_delete_transaction_requires_post(self):
        transaction = Transaction.objects.create(
            user=self.user,
            type='receita',
            amount='100.00',
            category=self.category,
            description='Salary',
        )

        response = self.client.get(reverse('delete_transaction', args=[transaction.id]))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Transaction.objects.filter(id=transaction.id).exists())

    def test_delete_transaction_via_post(self):
        transaction = Transaction.objects.create(
            user=self.user,
            type='receita',
            amount='100.00',
            category=self.category,
            description='Salary',
        )

        response = self.client.post(reverse('delete_transaction', args=[transaction.id]))

        self.assertRedirects(response, reverse('list_transactions'))
        self.assertFalse(Transaction.objects.filter(id=transaction.id).exists())

    def test_edit_transaction_page_loads(self):
        transaction = Transaction.objects.create(
            user=self.user,
            type='receita',
            amount='100.00',
            category=self.category,
            description='Salary',
            date='2026-04-01',
        )

        response = self.client.get(reverse('edit_transaction', args=[transaction.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Transaction')
        self.assertContains(response, 'Salary')

    def test_edit_transaction_updates_data(self):
        transaction = Transaction.objects.create(
            user=self.user,
            type='receita',
            amount='100.00',
            category=self.category,
            description='Salary',
            date='2026-04-01',
        )

        response = self.client.post(
            reverse('edit_transaction', args=[transaction.id]),
            {
                'type': 'despesa',
                'amount': '80.50',
                'category': self.category.id,
                'description': 'Supermarket',
                'date': '2026-04-02',
            },
        )

        self.assertRedirects(response, reverse('list_transactions'))
        transaction.refresh_from_db()
        self.assertEqual(transaction.type, 'despesa')
        self.assertEqual(transaction.amount, Decimal('80.50'))
        self.assertEqual(transaction.description, 'Supermarket')
        self.assertEqual(transaction.date.isoformat(), '2026-04-02')

    def test_edit_transaction_rejects_non_positive_amount(self):
        transaction = Transaction.objects.create(
            user=self.user,
            type='receita',
            amount='100.00',
            category=self.category,
            description='Salary',
            date='2026-04-01',
        )

        response = self.client.post(
            reverse('edit_transaction', args=[transaction.id]),
            {
                'type': 'receita',
                'amount': '0',
                'category': self.category.id,
                'description': 'Updated salary',
                'date': '2026-04-02',
            },
            follow=True,
        )

        self.assertContains(response, 'Transaction amount must be greater than zero.')
        transaction.refresh_from_db()
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.description, 'Salary')

    def test_edit_transaction_rejects_amount_above_limit(self):
        transaction = Transaction.objects.create(
            user=self.user,
            type='receita',
            amount='100.00',
            category=self.category,
            description='Salary',
            date='2026-04-01',
        )

        response = self.client.post(
            reverse('edit_transaction', args=[transaction.id]),
            {
                'type': 'receita',
                'amount': '999999999999999999999999',
                'category': self.category.id,
                'description': 'Huge amount',
                'date': '2026-04-02',
            },
            follow=True,
        )

        self.assertContains(response, 'The amount exceeds the supported limit.')
        transaction.refresh_from_db()
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.description, 'Salary')

    def test_edit_transaction_returns_404_for_missing_transaction(self):
        response = self.client.get(reverse('edit_transaction', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_dashboard_only_shows_logged_in_user_data(self):
        other_category = Category.objects.create(user=self.other_user, name='Travel')
        Transaction.objects.create(
            user=self.user,
            type='receita',
            amount='100.00',
            category=self.category,
            description='Salary',
            date='2026-04-01',
        )
        Transaction.objects.create(
            user=self.other_user,
            type='despesa',
            amount='75.00',
            category=other_category,
            description='Flight',
            date='2026-04-01',
        )

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'Salary')
        self.assertNotContains(response, 'Flight')
