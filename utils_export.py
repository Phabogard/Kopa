"""Fonctions partagées par les modules d'export (export.py, pdf_export.py)."""
import re
import unicodedata
import models
LIBELLE_SENS={models.Sens.PRET:"J'ai prêté",models.Sens.EMPRUNT:"J'ai emprunté"}
LIBELLE_STATUT={models.Statut.NON_PAYEE:"Non payée",models.Statut.PARTIELLE:"Partielle",models.Statut.EN_RETARD:"En retard",models.Statut.PAYEE:"Payée"}
def nom_fichier_sur(nom:str)->str:
    sans_accent=unicodedata.normalize("NFKD",nom).encode("ascii","ignore").decode()
    slug=re.sub(r"[^a-zA-Z0-9]+","-",sans_accent).strip("-").lower()
    return slug or "contact"
