from django.conf import settings

SAAS_BILLING = {
    'stripe': {
                'plan': 'saas_billing.StripeSubscriptionPlan',
                'cost': 'saas_billing.StripeSubscriptionPlanCost',
                'subscription': 'saas_billing.StripeSubscription'
            },
            'paypal': {
                'plan': 'saas_billing.PaypalSubscriptionPlan',
                'cost': 'saas_billing.PaypalSubscriptionPlanCost',
                'subscription': 'saas_billing.PaypalSubscription'
            }
}

SAAS_BILLING_AUTH = {
    'stripe': {
        'PUBLISHABLE_KEY': '',
        'LIVE_KEY': '',
        'CANCEL_URL': '',
        'SUCCESS_URL': ''
    },
    'paypal': {
        'CLIENT_ID': '',
        'CLIENT_SECRET': '',
        'CANCEL_URL': '',
        'SUCCESS_URL': ''
    }
}


def compile_settings():
    """Compiles and validates all package settings and defaults.
        Provides basic checks to ensure required settings are declared
        and applies defaults for all missing settings.
        Returns:
            dict: All possible Django Flexible Subscriptions settings.
    """
    saas_billing_models = getattr(
        settings, 'SAAS_BILLING_MODELS', SAAS_BILLING
    )
    saas_billing_auth = getattr(
        settings, 'SAAS_BILLING_AUTH', SAAS_BILLING_AUTH
    )
    return {
        'billing_models': saas_billing_models,
        'billing_auths': saas_billing_auth
    }


SETTINGS = compile_settings()
