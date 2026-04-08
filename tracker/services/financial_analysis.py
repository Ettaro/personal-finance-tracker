from django.db.models import Sum

from tracker.models import Transaction


def _build_insights(total_income, total_expense, balance, top_expense_categories):
    insights = []

    if top_expense_categories:
        top_category = top_expense_categories[0]
        insights.append(
            f"Sua maior categoria de gasto no periodo foi {top_category['category__name']}, com R$ {top_category['total']:.2f}."
        )

    if total_income > 0:
        expense_ratio = (total_expense / total_income) * 100
        insights.append(
            f"Suas despesas representam {expense_ratio:.2f}% da sua receita no periodo."
        )

    if balance > 0:
        insights.append("Seu saldo atual esta positivo.")
    elif balance < 0:
        insights.append("Seu saldo atual esta negativo. Vale revisar os gastos.")
    else:
        insights.append("Seu saldo atual esta zerado.")

    return insights


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

    insights = _build_insights(total_income, total_expense, balance, top_expense_categories)

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
        'insights': insights,
    }