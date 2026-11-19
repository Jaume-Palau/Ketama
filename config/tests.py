"""Ajustes de seguridad y proxy sin base de datos ni lectura del .env local."""
import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, SimpleTestCase


class ConfiguracionSeguridadTests(SimpleTestCase):
    def cargar(self, **variables):
        # Dominio y clave ficticios, solo en memoria; nunca se usa PostgreSQL.
        entorno = {"SECRET_KEY": "clave-ficticia-exclusiva-de-pruebas", **variables}
        with patch.dict(os.environ, entorno, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(str(Path(__file__).with_name("settings.py")))

    def produccion(self, **variables):
        return self.cargar(**{
            "DJANGO_ENV": "production", "ALLOWED_HOSTS": "ketama.test", **variables,
        })

    def respuesta(self, ajustes, **headers):
        claves = (
            "ALLOWED_HOSTS", "SECURE_SSL_REDIRECT", "SECURE_PROXY_SSL_HEADER",
            "SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE",
        )
        with self.settings(**{clave: ajustes[clave] for clave in claves}):
            request = RequestFactory().get("/acceso/", **headers)
            return SecurityMiddleware(lambda request: HttpResponse("ok"))(request)

    def test_desarrollo_conserva_http_y_no_confia_en_cabecera_proxy(self):
        ajustes = self.cargar(DEBUG="True", TRUST_PROXY_HTTPS="True")
        self.assertTrue(ajustes["DEBUG"])
        self.assertFalse(ajustes["SECURE_SSL_REDIRECT"])
        self.assertFalse(ajustes["SESSION_COOKIE_SECURE"])
        self.assertFalse(ajustes["CSRF_COOKIE_SECURE"])
        self.assertIsNone(ajustes["SECURE_PROXY_SSL_HEADER"])
        self.assertEqual(self.respuesta(ajustes, HTTP_HOST="localhost").status_code, 200)

    def test_debug_false_local_no_activa_https(self):
        ajustes = self.cargar(DEBUG="False")
        self.assertFalse(ajustes["DEBUG"])
        self.assertFalse(ajustes["SECURE_SSL_REDIRECT"])

    def test_hosts_y_origenes_se_leen_del_entorno_y_admiten_wifi(self):
        ajustes = self.cargar(
            ALLOWED_HOSTS=" localhost, 127.0.0.1, 192.0.2.25, ",
            CSRF_TRUSTED_ORIGINS=" http://192.0.2.25:8000, ",
        )
        self.assertEqual(ajustes["ALLOWED_HOSTS"], ["localhost", "127.0.0.1", "192.0.2.25"])
        self.assertEqual(ajustes["CSRF_TRUSTED_ORIGINS"], ["http://192.0.2.25:8000"])
        self.assertEqual(self.respuesta(ajustes, HTTP_HOST="192.0.2.25:8000").status_code, 200)

    def test_produccion_activa_cookies_secure_y_redireccion_https(self):
        ajustes = self.produccion()
        self.assertFalse(ajustes["DEBUG"])
        self.assertTrue(ajustes["SESSION_COOKIE_SECURE"])
        self.assertTrue(ajustes["CSRF_COOKIE_SECURE"])
        response = self.respuesta(ajustes, HTTP_HOST="ketama.test")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "https://ketama.test/acceso/")

    def test_proxy_solo_se_reconoce_con_autorizacion_explicita_en_produccion(self):
        headers = {"HTTP_HOST": "ketama.test", "HTTP_X_FORWARDED_PROTO": "https"}
        self.assertEqual(self.respuesta(self.produccion(), **headers).status_code, 301)
        ajustes = self.produccion(TRUST_PROXY_HTTPS="True")
        self.assertEqual(ajustes["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertEqual(self.respuesta(ajustes, **headers).status_code, 200)
        headers["HTTP_X_FORWARDED_PROTO"] = "http"
        self.assertEqual(self.respuesta(ajustes, **headers).status_code, 301)

    def test_produccion_acepta_origenes_https_explicitos(self):
        ajustes = self.produccion(CSRF_TRUSTED_ORIGINS=" https://ketama.test, ")
        self.assertEqual(ajustes["CSRF_TRUSTED_ORIGINS"], ["https://ketama.test"])

    def test_rechaza_configuraciones_de_produccion_inseguras(self):
        for variables in (
            {"DEBUG": "True"}, {"ALLOWED_HOSTS": ""}, {"ALLOWED_HOSTS": "*"},
            {"CSRF_TRUSTED_ORIGINS": "http://ketama.test"},
        ):
            with self.subTest(variables=variables), self.assertRaises(ImproperlyConfigured):
                self.produccion(**variables)
        with self.assertRaises(ImproperlyConfigured):
            self.cargar(DJANGO_ENV="production")

    def test_clave_obligatoria_y_entorno_validado(self):
        with self.assertRaises(ImproperlyConfigured):
            self.cargar(SECRET_KEY="")
        with self.assertRaises(ImproperlyConfigured):
            self.cargar(DJANGO_ENV="produccion")
