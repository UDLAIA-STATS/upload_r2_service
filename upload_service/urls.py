from django.urls import path
from .views import CloudflareStreamDirectUpload

urlpatterns = [
    path("upload/", CloudflareStreamDirectUpload.as_view(), name="cf_direct_upload"),
]
