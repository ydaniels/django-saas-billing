
from django.urls import path, include
from saas_billing import views
 

urlpatterns = [
    path('stripe/webhook',  views.StripeWebHook.as_view()),
    path('paypal/webhook',  views.PaypalWebHook.as_view()),
]
