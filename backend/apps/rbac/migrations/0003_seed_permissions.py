from django.db import migrations


PERMISSIONS = (
    ("organisations.manage", "Manage organisations", "platform"),
    ("staff.manage", "Manage staff", "platform"),
    ("rbac.manage", "Manage roles and permissions", "platform"),
    ("retail.products.view", "View products", "retail"),
    ("retail.products.create", "Create products", "retail"),
    ("retail.products.update", "Update products", "retail"),
    ("retail.stock.receive", "Receive stock", "retail"),
    ("retail.stock.adjustment.request", "Request stock adjustments", "retail"),
    ("retail.stock.adjustment.approve", "Approve stock adjustments", "retail"),
    ("retail.stock.adjustment.reject", "Reject stock adjustments", "retail"),
    ("retail.shifts.open", "Open cashier shifts", "retail"),
    ("retail.shifts.view", "View cashier shifts", "retail"),
    ("retail.shifts.close", "Close cashier shifts", "retail"),
    ("retail.sales.checkout", "Process sales", "retail"),
    ("retail.sales.collection", "Record customer collections", "retail"),
    ("retail.sales.payment", "Manage payments", "retail"),
    ("retail.sales.return", "Process returns", "retail"),
    ("retail.sales.refund", "Process refunds", "retail"),
    ("retail.sales.view", "View sales", "retail"),
    ("retail.reports.view", "View reports", "retail"),
    ("retail.expenses.view", "View expenses", "retail"),
    ("retail.expenses.create", "Record expenses", "retail"),
    ("retail.customers.view", "View customers", "retail"),
    ("retail.customers.create", "Create customers", "retail"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("rbac", "Permission")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    database = schema_editor.connection.alias

    permissions = []
    for codename, name, module in PERMISSIONS:
        permission, _ = Permission.objects.using(database).get_or_create(
            codename=codename,
            defaults={"name": name, "module": module, "is_active": True},
        )
        permissions.append(permission)

    for role in Role.objects.using(database).filter(is_system=True).iterator():
        existing_ids = set(
            RolePermission.objects.using(database)
            .filter(role_id=role.pk, organisation_id=role.organisation_id)
            .values_list("permission_id", flat=True)
        )
        RolePermission.objects.using(database).bulk_create(
            [
                RolePermission(
                    organisation_id=role.organisation_id,
                    role_id=role.pk,
                    permission_id=permission.pk,
                )
                for permission in permissions
                if permission.pk not in existing_ids
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0002_role_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_permissions, migrations.RunPython.noop),
    ]
