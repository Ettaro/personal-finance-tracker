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


CATEGORY_KEYWORDS = {
    'Food': (
        'restaurant',
        'restaurante',
        'miyagi',
        'food',
        'mercado',
        'supermercado',
        'padaria',
        'lanchonete',
        'sushi',
        'pizza',
        'ifood',
        'delivery',
        'caf',
    ),
    'Transport': (
        'uber',
        '99',
        'taxi',
        'fuel',
        'gasolina',
        'combustivel',
        'posto',
        'bus',
        'metro',
    ),
    'Leisure': (
        'cinema',
        'show',
        'bar',
        'game',
        'games',
        'steam',
        'teatro',
    ),
    'Salary': (
        'salary',
        'salario',
        'payroll',
        'wage',
        'deposito salario',
    ),
    'Health': (
        'doctor',
        'clinic',
        'hospital',
        'farmacia',
        'pharmacy',
        'medical',
        'medico',
        'dentist',
    ),
    'Subscriptions': (
        'netflix',
        'spotify',
        'prime',
        'youtube',
        'disney',
        'subscription',
        'assinatura',
    ),
    'Housing': (
        'rent',
        'aluguel',
        'condominio',
        'mortgage',
        'energia',
        'water',
        'internet',
    ),
    'Education': (
        'school',
        'curso',
        'college',
        'university',
        'book',
        'livro',
    ),
    'Shopping': (
        'shopping',
        'store',
        'loja',
        'amazon',
        'mercado livre',
        'clothes',
        'roupa',
    ),
}


CATEGORY_ALIASES = {
    'alimentacao': 'Food',
    'alimentação': 'Food',
    'comida': 'Food',
    'transporte': 'Transport',
    'lazer': 'Leisure',
    'salario': 'Salary',
    'salário': 'Salary',
    'saude': 'Health',
    'saúde': 'Health',
    'medico': 'Health',
    'médico': 'Health',
    'assinaturas': 'Subscriptions',
    'moradia': 'Housing',
    'educacao': 'Education',
    'educação': 'Education',
    'compras': 'Shopping',
    'outros': 'Other',
    'food': 'Food',
    'transport': 'Transport',
    'leisure': 'Leisure',
    'salary': 'Salary',
    'health': 'Health',
    'subscriptions': 'Subscriptions',
    'housing': 'Housing',
    'education': 'Education',
    'shopping': 'Shopping',
    'other': 'Other',
}


def create_default_categories_for_user(user):
    from tracker.models import Category

    for category_name in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(user=user, name=category_name)


def normalize_category_name(category_name):
    normalized = (category_name or '').strip().lower()
    return CATEGORY_ALIASES.get(normalized, category_name)


def find_category_by_name(categories, category_name):
    normalized_name = normalize_category_name(category_name)
    if not normalized_name:
        return None

    for category in categories:
        if category.name.lower() == normalized_name.lower():
            return category

    return None


def suggest_category(categories, *text_parts):
    searchable_text = ' '.join(str(part or '') for part in text_parts).lower()

    for category in categories:
        if category.name.lower() in searchable_text:
            return category

    for category_name, keywords in CATEGORY_KEYWORDS.items():
        category = find_category_by_name(categories, category_name)
        if category and any(keyword in searchable_text for keyword in keywords):
            return category

    return find_category_by_name(categories, 'Other')
