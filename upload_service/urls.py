from django.urls import path
from .views import CloudflareStreamDirectUpload, RegisterStreamResult

urlpatterns = [
    path("cf/direct-upload/", CloudflareStreamDirectUpload.as_view(), name="cf_direct_upload"),
    path("videos/register/", RegisterStreamResult.as_view(), name="register_video"),
]
