from django.db.models import Sum

from tracker.models import Transaction


def build_period_summary():
    total_income = Transaction.objects.filter(type='receita').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = Transaction.objects.filter(type='despesa').aggregate(Sum('amount'))['amount__sum'] or 0
    balance = total_income - total_expense

    top_expense_categories = (
        Transaction.objects.filter(type='despesa')
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )

    return {
        'summary': {
            'income': float(total_income),
            'expense': float(total_expense),
            'balance': float(balance),
        },
        'top_expense_categories': [
            {
                'category': item['category__name'],
                'total': float(item['total']),
            }
            for item in top_expense_categories
        ],
    }
