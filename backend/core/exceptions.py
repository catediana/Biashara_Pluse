from rest_framework.exceptions import APIException


class ConflictError(APIException):
    status_code = 409
    default_detail = "The request conflicts with the current resource state."
    default_code = "conflict"


class BusinessRuleError(APIException):
    status_code = 422
    default_detail = "The request violates a business rule."
    default_code = "business_rule_violation"
