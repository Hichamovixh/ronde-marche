import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import collecte  # noqa: E402


class Variation(unittest.TestCase):
    def test_pourcentage_a_sept_jours(self):
        serie = [("2026-10-26", 100.0), ("2026-10-30", 105.0), ("2026-11-02", 110.0)]
        self.assertEqual(collecte.variation_7j(serie, "pct"), 10.0)

    def test_taux_en_points(self):
        serie = [("2026-10-26", 3.0), ("2026-11-02", 3.25)]
        self.assertEqual(collecte.variation_7j(serie, "pts"), 0.25)

    def test_historique_trop_court(self):
        self.assertIsNone(collecte.variation_7j([("2026-11-01", 1.0), ("2026-11-02", 2.0)], "pct"))


class Sources(unittest.TestCase):
    def test_yahoo_ignore_les_valeurs_nulles(self):
        brut = {"chart": {"result": [{"timestamp": [1762128000, 1762214400, 1762300800],
                                      "indicators": {"quote": [{"close": [10.0, None, 12.0]}]}}]}}
        with mock.patch.object(collecte, "telecharger", return_value=json.dumps(brut)):
            self.assertEqual([v for _, v in collecte.yahoo("^GSPC")], [10.0, 12.0])

    def test_bce_csv(self):
        brut = "KEY,TIME_PERIOD,OBS_VALUE\nA,2026-11-02,1.08\nA,2026-11-03,\nA,2026-11-04,1.09\n"
        with mock.patch.object(collecte, "telecharger", return_value=brut):
            self.assertEqual(collecte.bce("EXR/D.USD"), [("2026-11-02", 1.08), ("2026-11-04", 1.09)])

    def test_repli_sur_la_seconde_source(self):
        serie = [("2026-10-26", 1.0), ("2026-11-02", 2.0)]
        fournisseurs = {"yahoo": mock.Mock(side_effect=OSError("403")), "stooq": mock.Mock(return_value=serie)}
        with mock.patch.dict(collecte.FOURNISSEURS, fournisseurs):
            resultat = collecte.recuperer(collecte.INSTRUMENTS[0])
        self.assertEqual(resultat["source"], "Stooq")


class Collecte(unittest.TestCase):
    def test_panne_conserve_la_valeur_precedente_signalee(self):
        precedent = {"instruments": [{"id": "sp500", "nom": "S&P 500", "valeur": 5000, "statut": "ok"}]}
        with mock.patch.object(collecte, "recuperer", side_effect=RuntimeError("panne")):
            donnees, reussites = collecte.collecter(precedent)
        self.assertEqual(reussites, 0)
        self.assertEqual(donnees["instruments"], [{**precedent["instruments"][0], "statut": "ancien"}])

    def test_valeur_aberrante_rejetee(self):
        with self.assertRaises(ValueError):
            collecte.construire(collecte.INSTRUMENTS[0], [("2026-11-01", 1.0), ("2026-11-02", 0.0)], "yahoo")

    def test_index_ne_garde_que_les_fichiers_dates(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "2026-11-09.md").write_text("# Ronde de marché – 9 novembre\n", "utf-8")
            (d / "2026-11-16.md").write_text("Sans titre\n", "utf-8")
            (d / "brouillon.md").write_text("# Non\n", "utf-8")
            index = collecte.indexer_rapports(d)
        self.assertEqual([r["date"] for r in index], ["2026-11-16", "2026-11-09"])
        self.assertEqual(index[1]["titre"], "Ronde de marché – 9 novembre")


if __name__ == "__main__":
    unittest.main()
