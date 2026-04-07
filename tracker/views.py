from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Category, Transaction


def dashboard(request):
    transactions = Transaction.objects.select_related('category').all().order_by('-date', '-id')
    total_receitas = Transaction.objects.filter(type='receita').aggregate(Sum('amount'))['amount__sum'] or 0
    total_despesas = Transaction.objects.filter(type='despesa').aggregate(Sum('amount'))['amount__sum'] or 0
    saldo = total_receitas - total_despesas
    total_transacoes = transactions.count()
    recent_transactions = transactions[:6]

    category_summary = (
        Transaction.objects.filter(type='despesa')
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )
    category_labels = [item['category__name'] for item in category_summary]
    category_totals = [float(item['total']) for item in category_summary]
    comparison_labels = ['Receitas', 'Despesas']
    comparison_totals = [float(total_receitas), float(total_despesas)]

    monthly_summary = (
        Transaction.objects.values('type')
        .annotate(total=Sum('amount'), quantidade=Count('id'))
        .order_by('type')
    )
    monthly_summary_map = {item['type']: item for item in monthly_summary}

    context = {
        'total_receitas': total_receitas,
        'total_despesas': total_despesas,
        'saldo': saldo,
        'total_transacoes': total_transacoes,
        'recent_transactions': recent_transactions,
        'receitas_count': monthly_summary_map.get('receita', {}).get('quantidade', 0),
        'despesas_count': monthly_summary_map.get('despesa', {}).get('quantidade', 0),
        'category_labels': category_labels,
        'category_totals': category_totals,
        'comparison_labels': comparison_labels,
        'comparison_totals': comparison_totals,
    }
    return render(request, 'tracker/dashboard.html', context)


def list_transactions(request):
    transactions = Transaction.objects.select_related('category').all().order_by('-date', '-id')
    categories = Category.objects.all().order_by('name')

    if request.method == 'POST':
        transaction_type = request.POST.get('type', '').strip()
        amount_raw = request.POST.get('amount', '').strip()
        category_id = request.POST.get('category')
        description = request.POST.get('description', '').strip()
        date = request.POST.get('date')

        if not categories.exists():
            messages.error(request, 'Crie uma categoria antes de adicionar transacoes.')
            return redirect('list_transactions')

        if transaction_type not in dict(Transaction.TRANSACTION_TYPES):
            messages.error(request, 'Tipo de transacao invalido.')
            return redirect('list_transactions')

        if not description:
            messages.error(request, 'A descricao da transacao e obrigatoria.')
            return redirect('list_transactions')

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, TypeError):
            messages.error(request, 'Informe um valor valido para a transacao.')
            return redirect('list_transactions')

        if amount <= 0:
            messages.error(request, 'O valor da transacao deve ser maior que zero.')
            return redirect('list_transactions')

        category = get_object_or_404(Category, id=category_id)
        transaction = Transaction(
            type=transaction_type,
            amount=amount,
            category=category,
            description=description,
            date=date or None,
        )
        try:
            transaction.full_clean()
        except ValidationError:
            messages.error(request, 'O valor informado excede o limite suportado. Use no maximo 8 digitos antes da virgula e 2 depois.')
            return redirect('list_transactions')

        transaction.save()
        messages.success(request, 'Transacao adicionada com sucesso.')
        return redirect('list_transactions')

    return render(request, 'tracker/transactions.html', {'transactions': transactions, 'categories': categories})


def list_categories(request):
    categories = Category.objects.all().order_by('name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()

        if not name:
            messages.error(request, 'O nome da categoria e obrigatorio.')
            return redirect('list_categories')

        if Category.objects.filter(name__iexact=name).exists():
            messages.error(request, 'Ja existe uma categoria com esse nome.')
            return redirect('list_categories')

        Category.objects.create(name=name)
        messages.success(request, 'Categoria criada com sucesso.')
        return redirect('list_categories')

    return render(request, 'tracker/categories.html', {'categories': categories})


@require_POST
def delete_transaction(request, id):
    transaction = get_object_or_404(Transaction, id=id)
    transaction.delete()
    messages.success(request, 'Transacao removida com sucesso.')
    return redirect('list_transactions')


def edit_transaction(request, id):
    transaction = get_object_or_404(Transaction, id=id)
    categories = Category.objects.all().order_by('name')

    if request.method == 'POST':
        transaction_type = request.POST.get('type', '').strip()
        amount_raw = request.POST.get('amount', '').strip()
        category_id = request.POST.get('category')
        description = request.POST.get('description', '').strip()
        date = request.POST.get('date')

        if transaction_type not in dict(Transaction.TRANSACTION_TYPES):
            messages.error(request, 'Tipo de transacao invalido.')
            return redirect('edit_transaction', id=transaction.id)

        if not description:
            messages.error(request, 'A descricao da transacao e obrigatoria.')
            return redirect('edit_transaction', id=transaction.id)

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, TypeError):
            messages.error(request, 'Informe um valor valido para a transacao.')
            return redirect('edit_transaction', id=transaction.id)

        if amount <= 0:
            messages.error(request, 'O valor da transacao deve ser maior que zero.')
            return redirect('edit_transaction', id=transaction.id)

        category = get_object_or_404(Category, id=category_id)

        transaction.type = transaction_type
        transaction.amount = amount
        transaction.category = category
        transaction.description = description
        transaction.date = date or transaction.date

        try:
            transaction.full_clean()
        except ValidationError:
            messages.error(request, 'O valor informado excede o limite suportado.')
            return redirect('edit_transaction', id=transaction.id)

        transaction.save()
        messages.success(request, 'Transacao atualizada com sucesso.')
        return redirect('list_transactions')

    context = {
        'transaction': transaction,
        'categories': categories,
    }
    return render(request, 'tracker/edit_transaction.html', context)
