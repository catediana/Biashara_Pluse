from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.organisations.models import Branch, Membership, Organisation
from apps.rbac.models import Role


User = get_user_model()


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = (
            "id",
            "name",
            "slug",
            "sector",
            "country_code",
            "currency",
            "timezone",
        )
        read_only_fields = ("id", "slug")


class OrganisationCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    sector = serializers.ChoiceField(choices=Organisation.Sector.choices)
    country_code = serializers.RegexField(r"^[A-Za-z]{2}$", default="KE")
    currency = serializers.RegexField(r"^[A-Za-z]{3}$", default="KES")
    timezone = serializers.CharField(max_length=64, default="Africa/Nairobi")

    def validate_name(self, value):
        name = " ".join(value.split())
        if not name:
            raise serializers.ValidationError("Enter an organisation name.")
        return name

    def validate_country_code(self, value):
        return value.upper()

    def validate_currency(self, value):
        return value.upper()


class MembershipCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role_id = serializers.UUIDField()
    all_branches = serializers.BooleanField(default=True)
    branch_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )

    def validate_email(self, value):
        return value.strip().casefold()

    def validate(self, attrs):
        organisation = self.context["organisation"]
        role = Role.objects.for_organisation(organisation).filter(
            pk=attrs["role_id"],
            is_active=True,
            is_system=False,
        ).first()
        if role is None:
            raise serializers.ValidationError(
                {"role_id": "Choose an active, non-system role in this organisation."}
            )
        email_field = User.get_email_field_name()
        user = User._default_manager.filter(
            **{f"{email_field}__iexact": attrs["email"], "is_active": True}
        ).first()
        if user is None:
            raise serializers.ValidationError(
                {"email": "No active account exists for this email address."}
            )
        if Membership.objects.for_organisation(organisation).filter(user=user).exists():
            raise serializers.ValidationError(
                {"email": "This user is already a member of the organisation."}
            )
        attrs["user"] = user
        attrs["role"] = role
        branch_ids = set(attrs.get("branch_ids", []))
        branches = Branch.objects.for_organisation(organisation).filter(
            pk__in=branch_ids,
            is_active=True,
        )
        if {branch.pk for branch in branches} != branch_ids:
            raise serializers.ValidationError(
                {"branch_ids": "Choose active branches in this organisation."}
            )
        if not attrs["all_branches"] and not branch_ids:
            raise serializers.ValidationError(
                {"branch_ids": "Choose at least one branch or enable all branches."}
            )
        attrs["branch_ids"] = list(branch_ids)
        if attrs["all_branches"]:
            attrs["branch_ids"] = []
        return attrs


class MembershipUpdateSerializer(serializers.Serializer):
    role_id = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(
        choices=Membership.Status.choices,
        required=False,
    )
    all_branches = serializers.BooleanField(required=False)
    branch_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )

    def validate_role_id(self, value):
        role = Role.objects.for_organisation(
            self.context["organisation"]
        ).filter(pk=value, is_active=True).first()
        if role is None:
            raise serializers.ValidationError(
                "Choose an active role in this organisation."
            )
        return role

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Provide at least one membership field to update."
            )
        if attrs.get("role_id") and attrs["role_id"].is_system:
            raise serializers.ValidationError(
                {"role_id": "System roles cannot be assigned to staff."}
            )
        branch_ids = set(attrs.get("branch_ids", []))
        if "branch_ids" in attrs:
            branches = Branch.objects.for_organisation(
                self.context["organisation"]
            ).filter(pk__in=branch_ids, is_active=True)
            if {branch.pk for branch in branches} != branch_ids:
                raise serializers.ValidationError(
                    {"branch_ids": "Choose active branches in this organisation."}
                )
        membership = self.context["membership"]
        allowed_all_branches = attrs.get("all_branches", membership.all_branches)
        current_ids = set(
            membership.branch_grants.values_list("branch_id", flat=True)
        )
        selected_ids = attrs.get("branch_ids", current_ids)
        if not allowed_all_branches and not selected_ids:
            raise serializers.ValidationError(
                {"branch_ids": "Choose at least one branch or enable all branches."}
            )
        if "branch_ids" in attrs:
            attrs["branch_ids"] = list(branch_ids)
        return attrs


def serialize_membership(membership):
    user = membership.user
    return {
        "id": str(membership.pk),
        "user": {
            "id": str(user.pk),
            "email": getattr(user, User.get_email_field_name(), ""),
            "first_name": getattr(user, "first_name", ""),
            "last_name": getattr(user, "last_name", ""),
        },
        "role": {
            "id": str(membership.role_id),
            "name": membership.role.name,
            "is_system": membership.role.is_system,
        },
        "status": membership.status,
        "all_branches": membership.all_branches,
        "branch_ids": [
            str(branch_id)
            for branch_id in membership.branch_grants.values_list(
                "branch_id", flat=True
            )
        ],
        "joined_at": membership.joined_at,
    }
