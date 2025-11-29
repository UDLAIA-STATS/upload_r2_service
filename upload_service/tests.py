from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from upload_service.models import Video
from django.conf import settings

import upload_service.views as views


class CloudflareDirectUploadTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("cf_direct_upload")

        # Guardar referencias originales para restaurar al final
        self.original_config = views.config
        self.original_requests_post = views.requests.post

    def tearDown(self):
        # Restaurar los métodos reales
        views.config = self.original_config
        views.requests.post = self.original_requests_post

    def test_cloudflare_not_configured(self):
        """Debe devolver 500 si no existe configuración"""

        def fake_config(key):
            return None  # siempre devuelve None

        views.config = fake_config

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_cloudflare_direct_upload_success(self):
        """Debe devolver 200 con JSON válido"""

        def fake_config(key):
            data = {
                "R2_ACCOUNT_ID": "123",
                "R2_ACCESS_TOKEN": "abc"
            }
            return data.get(key)

        class FakeResponse:
            status_code = 200
            def json(self):
                return {"success": True, "result": {"uploadURL": "https://fake.com/upload"}}

        def fake_post(url, json, headers):
            return FakeResponse()

        views.config = fake_config
        views.requests.post = fake_post

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)

    def test_cloudflare_invalid_json(self):
        """Debe devolver 502 si Cloudflare envía JSON inválido"""

        def fake_config(key):
            return "dummy"

        class FakeResponse:
            def json(self):
                raise ValueError("Invalid JSON")

        def fake_post(url, json, headers):
            return FakeResponse()

        views.config = fake_config
        views.requests.post = fake_post

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)


class RegisterStreamResultTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("register_video")

    def test_register_video_success(self):
        """Registro exitoso"""

        payload = {
            "title": "Video Test",
            "description": "Desc test",
            "stream_id": "s001"
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Video.objects.count(), 1)

    def test_register_video_missing_stream_id(self):
        """Debe fallar sin stream_id"""

        payload = {"title": "Sin stream"}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_video_duplicate_stream_id(self):
        """Debe fallar si el stream_id ya existe"""

        Video.objects.create(stream_id="dup001")

        payload = {"stream_id": "dup001"}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_video_invalid_long_stream_id(self):
        """stream_id demasiado largo (>255 chars)"""

        payload = {"stream_id": "a" * 260}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
