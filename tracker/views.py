import base64
import binascii
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Category, Transaction
from .services.financial_analysis import build_period_summary
from .services.category_classifier import (
    create_default_categories_for_user,
    find_category_by_name,
    suggest_category,
)
from .services.recibos.asprise_client import extract_receipt_with_asprise
from .services.recibos.document_parser import (
    extract_text_from_receipt,
    extract_receipt_ocr_variants,
    image_file_to_base64,
    parse_receipt_ocr_payload,
    parse_receipt_text,
    preprocess_receipt_image,
)
from .services.recibos.receipt_ai_mapper import map_receipt_fields_with_ai


@login_required
def dashboard(request):
    analysis_data = build_period_summary(request.user)

    transactions = (
        Transaction.objects.select_related('category')
        .filter(user=request.user)
        .order_by('-date', '-id')
    )
    total_receitas = transactions.filter(type='receita').aggregate(Sum('amount'))['amount__sum'] or 0
    total_despesas = transactions.filter(type='despesa').aggregate(Sum('amount'))['amount__sum'] or 0
    saldo = total_receitas - total_despesas
    total_transacoes = transactions.count()
    recent_transactions = transactions[:6]

    category_summary = (
        transactions.filter(type='despesa')
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )
    category_labels = [item['category__name'] for item in category_summary]
    category_totals = [float(item['total']) for item in category_summary]
    comparison_labels = ['Income', 'Expenses']
    comparison_totals = [float(total_receitas), float(total_despesas)]

    monthly_summary = (
        transactions.values('type')
        .annotate(total=Sum('amount'), quantidade=Count('id'))
        .order_by('type')
    )
    monthly_summary_map = {item['type']: item for item in monthly_summary}

    financial_insights = analysis_data['insights']

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
        'financial_insights': financial_insights,
    }
    return render(request, 'tracker/dashboard.html', context)


@login_required
def list_transactions(request):
    transactions = (
        Transaction.objects.select_related('category')
        .filter(user=request.user)
        .order_by('-date', '-id')
    )
    categories = Category.objects.filter(user=request.user).order_by('name')

    if request.method == 'POST':
        transaction_type = request.POST.get('type', '').strip()
        amount_raw = request.POST.get('amount', '').strip()
        category_id = request.POST.get('category')
        description = request.POST.get('description', '').strip()
        date = request.POST.get('date')

        if not categories.exists():
            messages.error(request, 'Create a category before adding transactions.')
            return redirect('list_transactions')

        if transaction_type not in dict(Transaction.TRANSACTION_TYPES):
            messages.error(request, 'Invalid transaction type.')
            return redirect('list_transactions')

        if not description:
            messages.error(request, 'Transaction description is required.')
            return redirect('list_transactions')

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, TypeError):
            messages.error(request, 'Enter a valid amount for the transaction.')
            return redirect('list_transactions')

        if amount <= 0:
            messages.error(request, 'Transaction amount must be greater than zero.')
            return redirect('list_transactions')

        category = get_object_or_404(Category, id=category_id, user=request.user)
        transaction = Transaction(
            type=transaction_type,
            user=request.user,
            amount=amount,
            category=category,
            description=description,
            date=date or None,
        )
        try:
            transaction.full_clean()
        except ValidationError:
            messages.error(request, 'The amount exceeds the supported limit. Use at most 8 digits before the decimal separator and 2 after it.')
            return redirect('list_transactions')

        transaction.save()
        messages.success(request, 'Transaction added successfully.')
        return redirect('list_transactions')

    return render(request, 'tracker/transactions.html', {'transactions': transactions, 'categories': categories})


@login_required
def list_categories(request):
    categories = Category.objects.filter(user=request.user).order_by('name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()

        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('list_categories')

        if Category.objects.filter(user=request.user, name__iexact=name).exists():
            messages.error(request, 'A category with this name already exists.')
            return redirect('list_categories')

        Category.objects.create(user=request.user, name=name)
        messages.success(request, 'Category created successfully.')
        return redirect('list_categories')

    return render(request, 'tracker/categories.html', {'categories': categories})


@require_POST
@login_required
def edit_category(request, id):
    category = get_object_or_404(Category, id=id, user=request.user)
    name = request.POST.get('name', '').strip()

    if not name:
        messages.error(request, 'Category name is required.')
        return redirect('list_categories')

    duplicate_exists = (
        Category.objects
        .filter(user=request.user, name__iexact=name)
        .exclude(id=category.id)
        .exists()
    )
    if duplicate_exists:
        messages.error(request, 'A category with this name already exists.')
        return redirect('list_categories')

    category.name = name
    category.save()
    messages.success(request, 'Category updated successfully.')
    return redirect('list_categories')


@require_POST
@login_required
def delete_category(request, id):
    category = get_object_or_404(Category, id=id, user=request.user)

    if Transaction.objects.filter(user=request.user, category=category).exists():
        messages.error(request, 'This category has transactions and cannot be deleted.')
        return redirect('list_categories')

    category.delete()
    messages.success(request, 'Category removed successfully.')
    return redirect('list_categories')


@require_POST
@login_required
def delete_transaction(request, id):
    transaction = get_object_or_404(Transaction, id=id, user=request.user)
    transaction.delete()
    messages.success(request, 'Transaction removed successfully.')
    return redirect('list_transactions')


@login_required
def edit_transaction(request, id):
    transaction = get_object_or_404(Transaction, id=id, user=request.user)
    categories = Category.objects.filter(user=request.user).order_by('name')

    if request.method == 'POST':
        transaction_type = request.POST.get('type', '').strip()
        amount_raw = request.POST.get('amount', '').strip()
        category_id = request.POST.get('category')
        description = request.POST.get('description', '').strip()
        date = request.POST.get('date')

        if transaction_type not in dict(Transaction.TRANSACTION_TYPES):
            messages.error(request, 'Invalid transaction type.')
            return redirect('edit_transaction', id=transaction.id)

        if not description:
            messages.error(request, 'Transaction description is required.')
            return redirect('edit_transaction', id=transaction.id)

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, TypeError):
            messages.error(request, 'Enter a valid amount for the transaction.')
            return redirect('edit_transaction', id=transaction.id)

        if amount <= 0:
            messages.error(request, 'Transaction amount must be greater than zero.')
            return redirect('edit_transaction', id=transaction.id)

        category = get_object_or_404(Category, id=category_id, user=request.user)

        transaction.type = transaction_type
        transaction.amount = amount
        transaction.category = category
        transaction.description = description
        transaction.date = date or transaction.date

        try:
            transaction.full_clean()
        except ValidationError:
            messages.error(request, 'The amount exceeds the supported limit.')
            return redirect('edit_transaction', id=transaction.id)

        transaction.save()
        messages.success(request, 'Transaction updated successfully.')
        return redirect('list_transactions')

    context = {
        'transaction': transaction,
        'categories': categories,
    }
    return render(request, 'tracker/edit_transaction.html', context)

def financial_analysis_preview(request):
    data = build_period_summary(request.user)
    return JsonResponse(data)


def _normalize_imported_amount(amount_raw):
    normalized_amount = (amount_raw or '').strip().replace('R$', '').replace(' ', '')
    normalized_amount = normalized_amount.replace('.', '').replace(',', '.')
    return Decimal(normalized_amount)


def _normalize_imported_date(date_raw):
    normalized_date = (date_raw or '').strip()
    if not normalized_date:
        return ''

    try:
        return datetime.strptime(normalized_date, '%d/%m/%Y').date().isoformat()
    except ValueError:
        return normalized_date


def _suggest_category(categories, description):
    category = suggest_category(categories, description)
    return category.id if category else ''


def _find_category_by_name(categories, suggested_category_name):
    category = find_category_by_name(categories, suggested_category_name)
    return category.id if category else ''


def _build_receipt_import_context(user, uploaded_file):
    categories = Category.objects.filter(user=user).order_by('name')
    processed_image = preprocess_receipt_image(uploaded_file)
    processed_image_base64 = image_file_to_base64(processed_image)

    parsed_data = None
    extracted_text = ''
    ocr_variants = None

    try:
        asprise_result = extract_receipt_with_asprise(processed_image)
    except Exception:
        asprise_result = None

    if asprise_result:
        parsed_data = asprise_result['parsed_data']
        extracted_text = parsed_data.get('ocr_text', '')
        ocr_variants = {
            'best_text': extracted_text,
            'best_source': 'asprise',
            'full_image_ocr': extracted_text,
            'cropped_image_ocr': '',
        }
    else:
        ocr_variants = extract_receipt_ocr_variants(processed_image)
        extracted_text = ocr_variants['best_text']
        parsed_data = parse_receipt_ocr_payload(ocr_variants)
        parsed_data = map_receipt_fields_with_ai(ocr_variants, parsed_data, categories)

    parsed_data['amount'] = parsed_data.get('amount', '')
    parsed_data['date'] = _normalize_imported_date(parsed_data.get('date', ''))
    parsed_data['type'] = parsed_data.get('type', 'despesa')
    parsed_data['category_id'] = _find_category_by_name(
        categories,
        parsed_data.get('suggested_category', ''),
    ) or _suggest_category(
        categories,
        ' '.join(
            str(value or '')
            for value in (
                parsed_data.get('description'),
                parsed_data.get('ocr_text'),
                extracted_text,
            )
        ),
    )

    return {
        'categories': categories,
        'ocr_variants': ocr_variants,
        'processed_image_base64': processed_image_base64,
        'extracted_text': extracted_text,
        'parsed_data': parsed_data,
    }


@login_required
def import_receipt(request):
    return redirect('receipt_scan')


@login_required
def receipt_scan(request):
    if request.method == 'POST':
        captured_image_data = request.POST.get('captured_image_data', '').strip()

        if not captured_image_data:
            messages.error(request, 'Capture a photo before continuing.')
            return redirect('receipt_scan')

        try:
            _, encoded_image = captured_image_data.split(',', 1)
            image_bytes = base64.b64decode(encoded_image)
        except (ValueError, binascii.Error):
            messages.error(request, 'The captured image could not be processed. Try taking the photo again.')
            return redirect('receipt_scan')

        uploaded_file = ContentFile(image_bytes, name='receipt_scan.png')
        context = _build_receipt_import_context(request.user, uploaded_file)
        return render(request, 'tracker/import_receipt_result.html', context)

    return render(request, 'tracker/receipt_scan.html')


@require_POST
@login_required
def save_imported_receipt(request):
    categories = Category.objects.filter(user=request.user).order_by('name')
    description = request.POST.get('description', '').strip()
    amount_raw = request.POST.get('amount', '').strip()
    transaction_type = request.POST.get('type', '').strip()
    category_id = request.POST.get('category')
    date = request.POST.get('date', '').strip()

    if not categories.exists():
        messages.error(request, 'Create a category before importing a transaction from a receipt.')
        return redirect('list_categories')

    if transaction_type not in dict(Transaction.TRANSACTION_TYPES):
        messages.error(request, 'Invalid transaction type.')
        return redirect('import_receipt')

    if not description:
        messages.error(request, 'Transaction description is required.')
        return redirect('import_receipt')

    try:
        amount = _normalize_imported_amount(amount_raw)
    except (InvalidOperation, TypeError):
        messages.error(request, 'Could not interpret the receipt amount. Review the field before saving.')
        return redirect('import_receipt')

    if amount <= 0:
        messages.error(request, 'Transaction amount must be greater than zero.')
        return redirect('import_receipt')

    category = get_object_or_404(Category, id=category_id, user=request.user)
    transaction = Transaction(
        type=transaction_type,
        user=request.user,
        amount=amount,
        category=category,
        description=description,
        date=date or None,
    )

    try:
        transaction.full_clean()
    except ValidationError:
        messages.error(request, 'Imported data could not be saved. Review the amount, date, and category.')
        return redirect('import_receipt')

    transaction.save()
    messages.success(request, 'Transaction imported successfully from the receipt.')
    return redirect('list_transactions')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        messages.success(request, 'You are now signed in.')
        return redirect('dashboard')

    return render(request, 'tracker/login.html', {'form': form})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data.get('username', '').strip()
        if username and form._meta.model.objects.filter(username__iexact=username).exists():
            form.add_error('username', 'An account with this username already exists.')
            return render(request, 'tracker/signup.html', {'form': form})

        try:
            user = form.save()
        except IntegrityError:
            form.add_error('username', 'An account with this username already exists.')
            return render(request, 'tracker/signup.html', {'form': form})

        create_default_categories_for_user(user)
        login(request, user)
        messages.success(request, 'Your account has been created successfully.')
        return redirect('dashboard')

    return render(request, 'tracker/signup.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been signed out.')
    return redirect('login')
