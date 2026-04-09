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
            f"Sua maior categoria de gasto no periodo foi {top_category['category__name']}, com {_format_currency(top_category_total)}."
        )

        if total_expense > 0:
            top_category_ratio = (top_category_total / total_expense) * 100
            if top_category_ratio >= 40:
                insights.append(
                    f"Os gastos com {top_category['category__name']} concentram {top_category_ratio:.2f}% das suas despesas."
                )

    if total_income > 0:
        expense_ratio = (total_expense / total_income) * 100
        insights.append(
            f"No periodo atual, as despesas consumiram {_format_percentage(expense_ratio)} da sua receita."
        )

        if expense_ratio >= 80:
            insights.append(
                "Suas despesas estao consumindo grande parte da sua receita."
            )
    else:
        insights.append(
            "Nao ha receitas registradas no periodo, entao a analise esta baseada apenas nas despesas."
        )

    if balance > 0:
        insights.append("Seu saldo atual permanece positivo.")
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