from django.urls import path
from .views import CloudflareVideoUpload, VideoKeyGenerate

urlpatterns = [
    path("upload/", CloudflareVideoUpload.as_view(), name="cf_direct_upload"),
    path("generate-key/", VideoKeyGenerate.as_view(), name="generate_video_key"),
]
