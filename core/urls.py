from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('panel/', views.panel, name='panel'),
    path('statements', views.list_statements_meta, name='statements_list'),
    path('statement/custom', views.statement_custom, name='statement_custom'),
    path('statement/<int:statement_id>', views.statement_meta, name='statement_meta'),
    path('statement/<int:statement_id>.pdf', views.statement_pdf, name='statement_pdf'),
    path('templates/<str:field>', views.templates_api, name='templates_api'),
]
