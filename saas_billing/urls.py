from django.urls import path, include

from rest_framework.routers import SimpleRouter
from . import views

app_name = 'saas_billing'

router = SimpleRouter()
router.register(r'payments', views.CryptoCurrencyPaymentViewset, basename='payments')
router.register('plan-costs', views.PlanCostCryptoUserSubscriptionView, basename='plan-costs')
router.register('transactions', views.SubscriptionTransactionPaymentViewSet, basename='transactions')
router.register('subscriptions', views.UserSubscriptionCrypto, basename='subscriptions')

urlpatterns = [
    path('cryptocurrency', include(router.urls)),
]

urlpatterns += router.urls
