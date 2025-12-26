from django.urls import path
from .views import CloudflareStreamDirectUpload, UploadProgressView

urlpatterns = [
    path("upload/", CloudflareStreamDirectUpload.as_view(), name="cf_direct_upload"),
    path("upload/progress/<str:key>/", UploadProgressView.as_view(), name="upload_progress"),
]
