from django.db.models import Sum

from tracker.models import Transaction

def _format_currency(value):
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"

def _format_percentage(value):
    formatted = f"{value:.2f}".replace(".", ",")
    return f"{formatted}%"

def _build_insights(total_income, total_expense, balance, top_expense_categories):
    insights = []

    if top_expense_categories:
        top_category = top_expense_categories[0]
        top_category_total = top_category['total']

        insights.append(
            f"Your highest spending category in this period was {top_category['category__name']}, with {_format_currency(top_category_total)}."
        )

        if total_expense > 0:
            top_category_ratio = (top_category_total / total_expense) * 100
            if top_category_ratio >= 40:
                insights.append(
                    f"Spending in {top_category['category__name']} accounts for {top_category_ratio:.2f}% of your total expenses."
                )

    if total_income > 0:
        expense_ratio = (total_expense / total_income) * 100
        insights.append(
            f"In the current period, expenses consumed {_format_percentage(expense_ratio)} of your income."
        )

        if expense_ratio >= 80:
            insights.append(
                "Your expenses are consuming a large share of your income."
            )
    else:
        insights.append(
            "There is no recorded income in this period, so the analysis is based only on expenses."
        )

    if balance > 0:
        insights.append("Your current balance remains positive.")
    elif balance < 0:
        insights.append("Your current balance is negative. It may be worth reviewing your spending.")
    else:
        insights.append("Your current balance is zero.")

    return insights


def build_period_summary(user):
    transactions = Transaction.objects.filter(user=user)
    total_income = transactions.filter(type='receita').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = transactions.filter(type='despesa').aggregate(Sum('amount'))['amount__sum'] or 0
    balance = total_income - total_expense

    top_expense_categories = (
        transactions.filter(type='despesa')
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
