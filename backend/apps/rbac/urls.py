from django.urls import path

from apps.rbac import views

app_name = "rbac"

urlpatterns = [
    path("permissions/", views.PermissionListView.as_view(), name="permissions"),
    path("roles/", views.RoleListCreateView.as_view(), name="roles"),
    path("roles/<uuid:role_id>/", views.RoleDetailView.as_view(), name="role_detail"),
]
