
from django.urls import path, include
from saas_billing import views
 

urlpatterns = [
    path('billing/stripe/webhook',  views.StripeWebHook.as_view()),
    path('billing/paypal/webhook',  views.PaypalWebHook.as_view()),
]
