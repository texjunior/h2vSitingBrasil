from django.test import SimpleTestCase
from .services.perfil_energetico import numero_valido, simular, PerfilEnergeticoErro

class PerfilEnergeticoTests(SimpleTestCase):
    def test_ignora_ausente_nasa(self):
        self.assertIsNone(numero_valido(-999))
        self.assertIsNone(numero_valido('abc'))

    def test_potencial_horario_gera_resultados(self):
        dados=[(m,h,0.65 if 7<=h<=17 else 0,5.0,7.5,27)
               for m in range(1,13) for _ in range(30) for h in range(24)]
        resultado=simular(dados,meta_kg_dia=10,painel_wp=600,turbina_kw=3000,quota_solar=50)
        self.assertGreaterEqual(resultado['h2_medio_dia_kg'],9.99)
        self.assertEqual(len(resultado['meses']),12)
        self.assertEqual(len(resultado['perfil_solar_24h']),24)

    def test_rejeita_meta_invalida(self):
        with self.assertRaises(PerfilEnergeticoErro):
            simular([],meta_kg_dia=-5)
