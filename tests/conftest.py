def pytest_configure():
    from django.conf import settings

    settings.configure(
        DEBUG_PROPAGATE_EXCEPTIONS=True,
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3',
                               'NAME': ':memory:'}},
        SITE_ID=1,
        SECRET_KEY='not very secret in tests',
        USE_I18N=True,
        USE_L10N=True,
        STATIC_URL='/static/',
        ROOT_URLCONF='tests.urls',
        TEMPLATE_LOADERS=(
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ),
        MIDDLEWARE_CLASSES=(
            'django.middleware.common.CommonMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
        ),
        INSTALLED_APPS=(
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.sites',
            'django.contrib.messages',
            'django.contrib.staticfiles',

            'rest_framework',
            'rest_framework.authtoken',
            'tests',
            'subscriptions_api',
            'cryptocurrency_payment',
            'saas_billing'
        ),
        PASSWORD_HASHERS=(
            'django.contrib.auth.hashers.SHA1PasswordHasher',
            'django.contrib.auth.hashers.PBKDF2PasswordHasher',
            'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
            'django.contrib.auth.hashers.BCryptPasswordHasher',
            'django.contrib.auth.hashers.MD5PasswordHasher',
            'django.contrib.auth.hashers.CryptPasswordHasher',
        ),
        CRYPTOCURRENCY_PAYMENT={
            "BITCOIN": {
                "CODE": "btc",
                "BACKEND": "merchant_wallet.backends.btc.BitcoinBackend",
                "FEE": 0.00,
                "REFRESH_PRICE_AFTER_MINUTE": 15,
                "REUSE_ADDRESS": False,
                "ACTIVE": True,
                "MASTER_PUBLIC_KEY": 'xpub6BfKpqjTwvH21wJGWEfxLppb8sU7C6FJge2kWb9315oP4ZVqCXG29cdUtkyu7YQhHyfA5nt63nzcNZHYmqXYHDxYo8mm1Xq1dAC7YtodwUR',
                "CANCEL_UNPAID_PAYMENT_HRS": 24,
                "CREATE_NEW_UNDERPAID_PAYMENT": True,
                "IGNORE_UNDERPAYMENT_AMOUNT": 10,
                "IGNORE_CONFIRMED_BALANCE_WITHOUT_SAVED_HASH_MINS": 20,
                "BALANCE_CONFIRMATION_NUM": 1,
                "ALLOW_ANONYMOUS_PAYMENT": True,
            },
        },
        EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend',
        SUBSCRIPTIONS_API_SUBSCRIPTIONTRANSACTION_MODEL='saas_billing.SubscriptionTransaction',
        STRIPE_PUBLISHABLE_KEY='',
        STRIPE_LIVE_KEY = '',
        PAYPAL_CLIENT_ID = '',
        PAYPAL_CLIENT_SECRET = '',
        SAAS_BILLING_MODELS = {
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
        },
        SAAS_BILLING_AUTH = {
            'stripe': {
                'PUBLISHABLE_KEY': '',
                'LIVE_KEY': '',
                'CANCEL_URL': 'https://google.com/cancel',
                'SUCCESS_URL': 'https://google.com/success'
            },
            'paypal': {
                'CLIENT_ID': '',
                'CLIENT_SECRET': '',
                'TOKEN': None,
                'ENV': 'dev',
                'CANCEL_URL': 'https://google.com/cancel',
                'SUCCESS_URL': 'https://google.com/success',
                'WEB_HOOK_ID': ''
            }
        }

    )

    try:
        import oauth_provider  # NOQA
        import oauth2  # NOQA
    except ImportError:
        pass
    else:
        settings.INSTALLED_APPS += (
            'oauth_provider',
        )

    try:
        import provider  # NOQA
    except ImportError:
        pass
    else:
        settings.INSTALLED_APPS += (
            'provider',
            'provider.oauth2',
        )

    # guardian is optional
    try:
        import guardian  # NOQA
    except ImportError:
        pass
    else:
        settings.ANONYMOUS_USER_ID = -1
        settings.AUTHENTICATION_BACKENDS = (
            'django.contrib.auth.backends.ModelBackend',
            'guardian.backends.ObjectPermissionBackend',
        )
        settings.INSTALLED_APPS += (
            'guardian',
        )
    try:
        import django
        django.setup()
    except AttributeError:
        pass
