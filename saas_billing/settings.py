import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_HOSTS = ['localhost:8000', 'localhost']
DEBUG = True
DEFAULT_FROM_EMAIL = 'webmaster@example.com'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
                         'NAME': os.path.join(BASE_DIR, 'db.sqlite3')}}
ROOT_URLCONF = 'saas_billing.urls'
SITE_ID = 1
SECRET_KEY = 'not very secret in tests'
USE_I18N = True
USE_L10N = True
STATIC_URL = '/static/'
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)
INSTALLED_APPS = (
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
)
PAYPAL_CLIENT_SECRET = 'EMgFt7kqJofYu9wmYPAcuCPLYiCquAwD4pTTc03vnxBVvVl9MGyhE1vQFe79Da9_544yZwcQx0EZs9fd',
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
}
SAAS_BILLING_AUTH = {
    'stripe': {
        'PUBLISHABLE_KEY': 'pk_test_51HNm2TArjZeWGURq8enbhcYGLaxt3adfY561ZnohjqQ8n0bDqn1GcRd6ObHuI7IDhrxeC7b6ruZVoENmfKT3w9Wr00hAMrun0a',
        'LIVE_KEY': 'sk_test_51HNm2TArjZeWGURqvcHDTQF5e32q9KezpGhAJGC36IKEeGfsCcWFwxr2O1oTEZvCGIPxiCJyNHviUFNkw04cQ6tP0064UD4Anp',
        'CANCEL_URL': '',
        'SUCCESS_URL': ''
    },
    'paypal': {
        'CLIENT_ID': 'AT-8PLSUWmfilh2zGNXA5QGqxniBvLjEG3fQJdvHZ44L7TDucKmcdWdVFEmGXpwAnu4vERown_esNiPj',
        'CLIENT_SECRET': 'EMgFt7kqJofYu9wmYPAcuCPLYiCquAwD4pTTc03vnxBVvVl9MGyhE1vQFe79Da9_544yZwcQx0EZs9fd',
        'TOKEN': None,
        'ENV': 'dev',
        'CANCEL_URL': 'https://google.com/cancel',
        'SUCCESS_URL': 'https://google.com/success',
        'WEB_HOOK_ID': ''
    }
}
# SUBSCRIPTIONS_API_USERSUBSCRIPTION_MODEL='saas_billing.usersubscription'
SUBSCRIPTIONS_API_SUBSCRIPTIONTRANSACTION_MODEL = 'saas_billing.SubscriptionTransaction'
