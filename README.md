# Ronde de marché

Site statique qui affiche l'évolution des marchés et la ronde d'analyse du lundi.

- `scripts/collecte.py` récupère les cours et écrit `site/data/`.
- `.github/workflows/site.yml` lance la collecte quatre fois par jour et publie le site sur GitHub Pages.
- `site/rapports/AAAA-MM-JJ.md` contient les rondes publiées.
- `site/alertes/AAAA-MM-JJTHH-MM-SS.txt` contient les alertes envoyées par n8n.

Tests : `python3 -m unittest discover -s tests`

Ce site donne une information générale et ne constitue pas un conseil en investissement personnalisé.
