from django.urls import path
from . import views

app_name = 'bestellung'

urlpatterns = [
    # Public views
    path('', views.order_form, name='order_form'),
    path('confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),

    # Admin - Template management
    path('admin/templates/', views.admin_template_list, name='admin_template_list'),
    path('admin/template/create/', views.admin_template_create, name='admin_template_create'),
    path('admin/template/<int:template_id>/edit/', views.admin_template_edit, name='admin_template_edit'),
    path('admin/template/<int:template_id>/items/', views.admin_menu_items, name='admin_menu_items'),
    path('admin/template/<int:template_id>/items/add/', views.create_menu_item_ajax, name='add_menu_item_ajax'),

    # Admin - Orders management
    path('admin/orders/', views.admin_orders_list, name='admin_orders_list'),
    path('admin/order/<int:order_id>/', views.admin_order_detail, name='admin_order_detail'),
    path('admin/orders/export/', views.admin_orders_export, name='admin_orders_export'),
]
