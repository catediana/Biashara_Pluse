from django.urls import path

from apps.organisations import views

app_name = "organisations"

urlpatterns = [
    path("", views.OrganisationListCreateView.as_view(), name="list_create"),
    path("members/", views.MembershipListCreateView.as_view(), name="members"),
    path(
        "members/<uuid:membership_id>/",
        views.MembershipDetailView.as_view(),
        name="member_detail",
    ),
    path("branches/", views.BranchListView.as_view(), name="branches"),
]
