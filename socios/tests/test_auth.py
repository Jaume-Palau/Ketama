"""Flujos de acceso con datos ficticios en la base de datos de pruebas."""
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from socios.models import Socio


class AutenticacionSociosTests(TestCase):
    password_inicial = "Temporal-De-Prueba-8x!"
    password_nueva = "Personal-De-Prueba-9z!"

    @classmethod
    def setUpTestData(cls):
        # Este 0 solo existe en la BD de pruebas; no se consulta el socio real.
        cls.usuario = User.objects.create_user(
            username="0", password=cls.password_inicial
        )
        cls.socio = Socio.objects.create(
            usuario=cls.usuario,
            nombre_completo="Socio de prueba",
            estado=Socio.Estado.ACTIVO,
        )
        cls.sin_perfil = User.objects.create_user(
            username="sin-perfil", password=cls.password_inicial
        )
        cls.personal = User.objects.create_user(
            username="personal", password=cls.password_inicial, is_staff=True
        )
        Socio.objects.create(
            usuario=cls.personal, nombre_completo="Personal de prueba"
        )
        cls.administrador = User.objects.create_superuser(
            username="administrador", password=cls.password_inicial
        )

    def acceder(self, **extra):
        return self.client.post(
            reverse("socios:login"),
            {"username": "0", "password": self.password_inicial, **extra},
        )

    def cambiar(self, **extra):
        return self.client.post(
            reverse("socios:cambiar_password"),
            {
                "old_password": self.password_inicial,
                "new_password1": self.password_nueva,
                "new_password2": self.password_nueva,
                **extra,
            },
        )

    def test_login_mantiene_campos_nativos_csrf_y_estilos_exclusivos(self):
        response = self.client.get(reverse("socios:login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "socios/login.html")
        for contenido in (
            'class="login-page"', 'css/login.css', 'name="csrfmiddlewaretoken"',
            'for="id_username"', 'for="id_password"', 'name="username"',
            'type="password"', 'autocomplete="username"',
            'autocomplete="current-password"', "Número de socio", "Entrar a Ketama",
        ):
            self.assertContains(response, contenido)
        self.assertNotContains(response, "css/catalogo.css")
        self.assertNotContains(response, "css/detalle.css")

    def test_login_muestra_error_y_conserva_numero_sin_exponer_password(self):
        password_incorrecta = "No-Debe-Mostrarse-83!"
        response = self.acceder(password=password_incorrecta)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertContains(response, 'class="login-alerta" role="alert"')
        self.assertContains(response, 'value="0"')
        self.assertNotContains(response, password_incorrecta)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_muestra_errores_de_campos_obligatorios(self):
        response = self.client.post(reverse("socios:login"), {})
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)
        self.assertIn("password", response.context["form"].errors)
        self.assertContains(response, 'class="login-error-campo" role="alert"')
        self.assertContains(response, 'aria-invalid="true"')

    def test_login_con_csrf_valido_conserva_cambio_obligatorio(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("socios:login"))
        token = client.cookies["csrftoken"].value
        response = client.post(reverse("socios:login"), {
            "username": "0", "password": self.password_inicial,
            "csrfmiddlewaretoken": token,
        })
        self.assertRedirects(response, reverse("socios:cambiar_password"))

    def test_estilos_de_acceso_se_comparten_sin_afectar_al_catalogo(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("socios:cambiar_password"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "css/login.css")
        self.assertContains(response, "css/cambiar_password.css")
        Socio.objects.filter(pk=self.socio.pk).update(debe_cambiar_password=False)
        response = self.client.get(reverse("geneticas:catalogo"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "css/catalogo.css")
        self.assertNotContains(response, "css/login.css")
        self.assertNotContains(response, "css/cambiar_password.css")

    def test_cambio_password_conserva_campos_ayudas_y_csrf_en_nuevo_diseno(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("socios:cambiar_password"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "socios/cambiar_password.html")
        self.assertContains(response, "Primer acceso")
        self.assertContains(response, 'type="password"', count=3)
        for campo in ("old_password", "new_password1", "new_password2"):
            self.assertContains(response, f'name="{campo}"')
            self.assertContains(response, f'for="id_{campo}"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, 'autocomplete="new-password"', count=2)
        self.assertContains(response, 'id="id_new_password1_helptext"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"', count=2)
        self.assertContains(response, 'action="' + reverse("socios:logout") + '"')
        self.assertContains(response, "Guardar contraseña")
        self.assertContains(response, "Cerrar sesión")
        self.assertNotContains(response, self.password_inicial)

    def test_cambio_password_muestra_errores_sin_exponer_contrasenas(self):
        self.client.force_login(self.usuario)
        response = self.cambiar(new_password1="123", new_password2="123")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertContains(response, 'class="login-error-campo" role="alert"')
        self.assertNotContains(response, self.password_inicial)

    def test_paginas_privadas_requieren_login(self):
        for nombre in ("inicio", "cambiar_password"):
            with self.subTest(nombre=nombre):
                response = self.client.get(reverse(f"socios:{nombre}"))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("socios:login")))

    def test_login_numero_cero_obliga_a_cambiar_sin_alterar_password(self):
        hash_anterior = self.usuario.password
        self.assertRedirects(self.acceder(), reverse("socios:cambiar_password"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.password, hash_anterior)

    def test_pendiente_no_puede_saltar_directamente_al_inicio(self):
        self.client.force_login(self.usuario)
        self.assertRedirects(
            self.client.get(reverse("socios:inicio")),
            reverse("socios:cambiar_password"),
        )

    def test_next_no_permite_saltar_cambio_ni_ir_al_admin_o_fuera(self):
        for destino in ("/", "/admin/", "https://example.com/"):
            with self.subTest(destino=destino):
                self.client.logout()
                self.assertRedirects(
                    self.acceder(next=destino), reverse("socios:cambiar_password")
                )

    def test_cambio_correcto_actualiza_hash_y_conserva_sesion(self):
        self.acceder()
        response = self.cambiar()
        self.assertRedirects(response, reverse("geneticas:catalogo"))
        self.usuario.refresh_from_db()
        self.socio.refresh_from_db()
        self.assertFalse(self.socio.debe_cambiar_password)
        self.assertTrue(self.usuario.check_password(self.password_nueva))
        self.assertFalse(self.usuario.check_password(self.password_inicial))
        self.assertNotEqual(self.usuario.password, self.password_nueva)
        self.assertContains(self.client.get(reverse("geneticas:catalogo")), "Catálogo")

    def test_nueva_sesion_tras_cambio_acepta_solo_password_nueva(self):
        self.acceder()
        self.cambiar()
        self.client.logout()
        self.assertEqual(self.acceder().status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(
            self.acceder(password=self.password_nueva), reverse("geneticas:catalogo")
        )

    def test_cambios_invalidos_no_modifican_hash_ni_indicador(self):
        self.acceder()
        hash_anterior = self.usuario.password
        for datos in (
            {"old_password": "incorrecta"},
            {"new_password2": "No-coincide-7!"},
            {"new_password1": "123", "new_password2": "123"},
            {
                "new_password1": self.password_inicial,
                "new_password2": self.password_inicial,
            },
        ):
            with self.subTest(datos=tuple(datos)):
                response = self.cambiar(**datos)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.usuario.refresh_from_db()
                self.socio.refresh_from_db()
                self.assertEqual(self.usuario.password, hash_anterior)
                self.assertTrue(self.socio.debe_cambiar_password)

    def test_login_sin_cambio_pendiente_va_al_inicio(self):
        self.socio.debe_cambiar_password = False
        self.socio.save(update_fields=["debe_cambiar_password"])
        self.assertRedirects(self.acceder(), reverse("geneticas:catalogo"))

    def test_password_incorrecta_no_inicia_sesion(self):
        response = self.acceder(password="incorrecta")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cuenta_deshabilitada_no_accede(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        self.assertEqual(self.acceder().status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deshabilitar_una_cuenta_bloquea_sesion_existente(self):
        self.acceder()
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        response = self.client.get(reverse("socios:inicio"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("socios:login")))

    def test_sin_perfil_y_cuentas_admin_no_acceden_por_login_socios(self):
        for usuario in (self.sin_perfil, self.personal, self.administrador):
            with self.subTest(usuario=usuario.username):
                response = self.client.post(
                    reverse("socios:login"),
                    {"username": usuario.username, "password": self.password_inicial},
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_sesion_admin_o_sin_perfil_no_abre_paginas_privadas(self):
        for usuario in (self.sin_perfil, self.personal, self.administrador):
            for nombre in ("inicio", "cambiar_password"):
                with self.subTest(usuario=usuario.username, nombre=nombre):
                    self.client.force_login(usuario)
                    self.assertEqual(
                        self.client.get(reverse(f"socios:{nombre}")).status_code, 403
                    )

    def test_cierre_de_sesion_solo_post_incluso_con_cambio_pendiente(self):
        self.acceder()
        self.assertEqual(self.client.get(reverse("socios:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(
            self.client.post(reverse("socios:logout")), reverse("socios:login")
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_mantiene_su_login_y_no_fuerza_cambio_de_socios(self):
        response = self.client.get(reverse("admin:login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/login.html")
        self.client.force_login(self.personal)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        self.socio.refresh_from_db()
        self.assertTrue(self.socio.debe_cambiar_password)

    def test_socio_no_puede_abrir_admin(self):
        self.acceder()
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("admin:login")))

    def test_logout_socios_no_cierra_una_sesion_admin(self):
        self.client.force_login(self.administrador)
        self.assertEqual(
            self.client.post(reverse("socios:logout")).status_code, 403
        )
        self.assertIn("_auth_user_id", self.client.session)

    def test_formularios_post_requieren_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(
            client.post(reverse("socios:login"), {}).status_code, 403
        )
        client.force_login(self.usuario)
        for nombre in ("cambiar_password", "logout"):
            with self.subTest(nombre=nombre):
                self.assertEqual(
                    client.post(reverse(f"socios:{nombre}"), {}).status_code, 403
                )

    def test_paginas_de_socios_no_se_guardan_en_cache(self):
        self.acceder()
        response = self.client.get(reverse("socios:cambiar_password"))
        self.assertIn("no-store", response.headers["Cache-Control"])
