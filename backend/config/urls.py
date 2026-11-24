from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/organisations/", include("apps.organisations.urls")),
    path("api/rbac/", include("apps.rbac.urls")),
    path("api/retail/", include("apps.retail.urls")),
    path("api/reporting/", include("apps.reporting.urls")),
]
