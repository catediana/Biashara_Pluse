from rest_framework import serializers

from apps.organisations.models import Branch


class ReportFilterSerializer(serializers.Serializer):
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.none(),
        required=False,
        source="branch",
    )
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
    export = serializers.ChoiceField(
        choices=("json", "csv"),
        default="json",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organisation = self.context["request"].active_organisation
        self.fields["branch_id"].queryset = Branch.objects.for_organisation(
            organisation
        ).filter(is_active=True)

    def validate(self, attrs):
        from_date = attrs.get("from_date")
        to_date = attrs.get("to_date")
        if from_date and to_date and from_date > to_date:
            raise serializers.ValidationError(
                {"from_date": "Start date must be on or before end date."}
            )
        return attrs
