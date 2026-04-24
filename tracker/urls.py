from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('transactions/', views.list_transactions, name='list_transactions'),
    path('transactions/delete/<int:id>/', views.delete_transaction, name='delete_transaction'),
    path('categories/', views.list_categories, name='list_categories'),
    path('transactions/edit/<int:id>/', views.edit_transaction, name='edit_transaction'),
    path('analysis/preview/', views.financial_analysis_preview, name='financial_analysis_preview'),
    path('import-receipt/', views.import_receipt, name='import_receipt'),
    path('import-receipt/save/', views.save_imported_receipt, name='save_imported_receipt'),
]
