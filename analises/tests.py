from django.test import TestCase


class PaginaInicialTests(TestCase):
    def test_pagina_inicial_carrega(self):
        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "H2V-Siting Brasil")

    def test_formulario_possui_csrf(self):
        resposta = self.client.get("/")
        self.assertContains(resposta, "csrfmiddlewaretoken")
