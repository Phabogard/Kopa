"""Export CSV de l'historique d'un contact (dettes + règlements)."""
import csv, io
from datetime import date, datetime
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
import models
from auth import get_current_user
from database import get_db
from utils_export import LIBELLE_SENS, LIBELLE_STATUT, nom_fichier_sur
router=APIRouter(prefix="/api",tags=["Export"])
EN_TETES=["type","id","sens","date","echeance","montant","devise","regle","restant","statut","note"]
def _montant(valeur:float,separateur:str)->str:
    texte=f"{valeur:.2f}"; return texte.replace(".",",") if separateur==";" else texte
def _charger_contact_du_proprietaire(db:Session,contact_id:int,utilisateur:models.User)->models.Contact:
    contact=db.query(models.Contact).options(joinedload(models.Contact.dettes).joinedload(models.Dette.reglements)).filter(models.Contact.id==contact_id,models.Contact.user_id==utilisateur.id).first()
    if contact is None: raise HTTPException(status_code=404,detail="Contact introuvable.")
    return contact
@router.get("/contacts/{contact_id}/export/csv",response_class=StreamingResponse,summary="Exporter l'historique d'un contact au format CSV")
def exporter_contact_csv(contact_id:int,separateur:str=Query(";",pattern=r"^[;,\t]$"),db:Session=Depends(get_db),utilisateur:models.User=Depends(get_current_user)):
    contact=_charger_contact_du_proprietaire(db,contact_id,utilisateur); tampon=io.StringIO(); tampon.write("\ufeff"); ecrivain=csv.writer(tampon,delimiter=separateur,lineterminator="\r\n")
    ecrivain.writerow(["Carnet de dettes — historique"]); ecrivain.writerow(["Contact",contact.nom]); ecrivain.writerow(["Téléphone",contact.telephone or ""]); ecrivain.writerow(["Export du",datetime.now().strftime("%d/%m/%Y %H:%M")]); ecrivain.writerow([]); ecrivain.writerow(EN_TETES)
    dettes=sorted(contact.dettes,key=lambda d:(d.date_operation,d.id))
    for dette in dettes:
        ecrivain.writerow(["DETTE",dette.id,LIBELLE_SENS[dette.sens],dette.date_operation.isoformat(),dette.date_echeance.isoformat() if dette.date_echeance else "",_montant(dette.montant,separateur),dette.devise,_montant(dette.montant_regle,separateur),_montant(dette.restant,separateur),LIBELLE_STATUT[dette.statut],(dette.note or "").replace("\n"," ")])
        for reglement in sorted(dette.reglements,key=lambda r:(r.date_reglement,r.id)):
            ecrivain.writerow(["REGLEMENT",reglement.id,f"Règlement de la dette #{dette.id}",reglement.date_reglement.isoformat(),"",_montant(reglement.montant,separateur),dette.devise,"","","",(reglement.note or "").replace("\n"," ")])
    ecrivain.writerow([]); ecrivain.writerow(["Totaux par devise"]); ecrivain.writerow(["devise","à percevoir","à payer","solde net"])
    for devise,ligne in sorted(contact.soldes.items()): ecrivain.writerow([devise,_montant(ligne["a_percevoir"],separateur),_montant(ligne["a_payer"],separateur),_montant(ligne["solde"],separateur)])
    tampon.seek(0); nom=f"carnet-{nom_fichier_sur(contact.nom)}-{date.today().isoformat()}.csv"
    return StreamingResponse(iter([tampon.getvalue()]),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="{nom}"; filename*=UTF-8\'\'{quote(nom)}'})
