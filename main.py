"""Carnet de Dettes — API FastAPI.

Lancement :  uvicorn main:app --reload
Docs       :  http://127.0.0.1:8000/docs
"""
import io
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from starlette.background import BackgroundTask
import auth
import export
import models
import pdf_export
import schemas
from database import Base, DATABASE_URL, engine, get_db
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Carnet de Dettes", description="Suivi des sommes prêtées et empruntées, multi-utilisateur.", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(export.router)
app.include_router(pdf_export.router)
def _get_contact(db: Session, contact_id: int, utilisateur: models.User) -> models.Contact:
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id, models.Contact.user_id == utilisateur.id).first()
    if contact is None: raise HTTPException(status_code=404, detail="Contact introuvable.")
    return contact
def _get_dette(db: Session, dette_id: int, utilisateur: models.User) -> models.Dette:
    dette = db.query(models.Dette).options(joinedload(models.Dette.contact), joinedload(models.Dette.reglements)).filter(models.Dette.id == dette_id, models.Dette.user_id == utilisateur.id).first()
    if dette is None: raise HTTPException(status_code=404, detail="Dette introuvable.")
    return dette
@app.get("/api/contacts", response_model=list[schemas.ContactOut], tags=["Contacts"])
def lister_contacts(q: Optional[str] = Query(None), db: Session = Depends(get_db), utilisateur: models.User = Depends(auth.get_current_user)):
    requete = db.query(models.Contact).options(joinedload(models.Contact.dettes).joinedload(models.Dette.reglements)).filter(models.Contact.user_id == utilisateur.id)
    if q:
        motif = f"%{q.strip()}%"
        requete = requete.filter(or_(models.Contact.nom.ilike(motif), models.Contact.telephone.ilike(motif)))
    return requete.order_by(models.Contact.nom.asc()).all()
@app.post("/api/contacts", response_model=schemas.ContactOut, status_code=status.HTTP_201_CREATED, tags=["Contacts"])
def creer_contact(payload: schemas.ContactCreate, db: Session = Depends(get_db), utilisateur: models.User = Depends(auth.get_current_user)):
    contact = models.Contact(**payload.model_dump(), user_id=utilisateur.id); db.add(contact); db.commit(); db.refresh(contact); return contact
@app.get("/api/contacts/{contact_id}", response_model=schemas.ContactOut, tags=["Contacts"])
def lire_contact(contact_id: int, db: Session = Depends(get_db), utilisateur: models.User = Depends(auth.get_current_user)): return _get_contact(db, contact_id, utilisateur)
@app.put("/api/contacts/{contact_id}", response_model=schemas.ContactOut, tags=["Contacts"])
def modifier_contact(contact_id: int, payload: schemas.ContactUpdate, db: Session = Depends(get_db), utilisateur: models.User = Depends(auth.get_current_user)):
    contact = _get_contact(db, contact_id, utilisateur)
    for champ, valeur in payload.model_dump(exclude_unset=True).items(): setattr(contact, champ, valeur)
    db.commit(); db.refresh(contact); return contact
@app.delete("/api/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Contacts"])
def supprimer_contact(contact_id: int, db: Session = Depends(get_db), utilisateur: models.User = Depends(auth.get_current_user)):
    contact = _get_contact(db, contact_id, utilisateur); db.delete(contact); db.commit()
@app.get("/api/dettes", response_model=list[schemas.DetteOut], tags=["Dettes"])
def lister_dettes(contact_id: Optional[int] = None, sens: Optional[models.Sens] = None, statut: Optional[models.Statut] = Query(None), devise: Optional[str] = None, q: Optional[str] = Query(None), db: Session = Depends(get_db), utilisateur: models.User = Depends(auth.get_current_user)):
    requete = db.query(models.Dette).options(joinedload(models.Dette.contact), joinedload(models.Dette.reglements)).filter(models.Dette.user_id == utilisateur.id)
    if contact_id is not None: _get_contact(db, contact_id, utilisateur); requete = requete.filter(models.Dette.contact_id == contact_id)
    if sens is not None: requete = requete.filter(models.Dette.sens == sens)
    if devise: requete = requete.filter(models.Dette.devise == devise.upper())
    if q:
        motif=f"%{q.strip()}%"; requete=requete.join(models.Contact).filter(or_(models.Dette.note.ilike(motif), models.Contact.nom.ilike(motif)))
    dettes=requete.order_by(models.Dette.date_operation.desc(), models.Dette.id.desc()).all()
    if statut is not None: dettes=[d for d in dettes if d.statut == statut]
    return dettes
@app.get("/api/dettes/echeances", response_model=list[schemas.DetteOut], tags=["Dettes"])
def dettes_echues(db: Session = Depends(get_db), utilisateur: models.User = Depends(auth.get_current_user)):
    dettes=db.query(models.Dette).options(joinedload(models.Dette.contact), joinedload(models.Dette.reglements)).filter(models.Dette.user_id == utilisateur.id, models.Dette.date_echeance.isnot(None), models.Dette.date_echeance <= date.today()).order_by(models.Dette.date_echeance.asc()).all()
    return [d for d in dettes if d.restant > 0.004]
@app.post("/api/dettes", response_model=schemas.DetteOut, status_code=status.HTTP_201_CREATED, tags=["Dettes"])
def creer_dette(payload: schemas.DetteCreate, db: Session = Depends(get_db), utilisateur: models.User = Depends(auth.get_current_user)):
    _get_contact(db,payload.contact_id,utilisateur); dette=models.Dette(**payload.model_dump(),user_id=utilisateur.id); db.add(dette); db.commit(); db.refresh(dette); return dette
@app.get("/api/dettes/{dette_id}", response_model=schemas.DetteOut, tags=["Dettes"])
def lire_dette(dette_id:int, db:Session=Depends(get_db), utilisateur:models.User=Depends(auth.get_current_user)): return _get_dette(db,dette_id,utilisateur)
@app.put("/api/dettes/{dette_id}", response_model=schemas.DetteOut, tags=["Dettes"])
def modifier_dette(dette_id:int,payload:schemas.DetteUpdate,db:Session=Depends(get_db),utilisateur:models.User=Depends(auth.get_current_user)):
    dette=_get_dette(db,dette_id,utilisateur); donnees=payload.model_dump(exclude_unset=True)
    if "contact_id" in donnees: _get_contact(db,donnees["contact_id"],utilisateur)
    if "montant" in donnees and donnees["montant"] < dette.montant_regle: raise HTTPException(status_code=400,detail=f"Le montant ne peut pas être inférieur aux règlements déjà enregistrés ({dette.montant_regle}).")
    for champ,valeur in donnees.items(): setattr(dette,champ,valeur)
    db.commit(); db.refresh(dette); return dette
@app.delete("/api/dettes/{dette_id}",status_code=status.HTTP_204_NO_CONTENT,tags=["Dettes"])
def supprimer_dette(dette_id:int,db:Session=Depends(get_db),utilisateur:models.User=Depends(auth.get_current_user)):
    dette=_get_dette(db,dette_id,utilisateur); db.delete(dette); db.commit()
@app.get("/api/dettes/{dette_id}/reglements",response_model=list[schemas.ReglementOut],tags=["Règlements"])
def lister_reglements(dette_id:int,db:Session=Depends(get_db),utilisateur:models.User=Depends(auth.get_current_user)): return _get_dette(db,dette_id,utilisateur).reglements
@app.post("/api/dettes/{dette_id}/reglements",response_model=schemas.DetteOut,status_code=status.HTTP_201_CREATED,tags=["Règlements"])
def enregistrer_reglement(dette_id:int,payload:schemas.ReglementCreate,db:Session=Depends(get_db),utilisateur:models.User=Depends(auth.get_current_user)):
    dette=_get_dette(db,dette_id,utilisateur)
    if payload.montant-dette.restant>0.004: raise HTTPException(status_code=400,detail=f"Le règlement dépasse le reste dû ({dette.restant} {dette.devise}).")
    db.add(models.Reglement(dette_id=dette.id,**payload.model_dump())); db.commit(); db.refresh(dette); return dette
@app.delete("/api/reglements/{reglement_id}",status_code=status.HTTP_204_NO_CONTENT,tags=["Règlements"])
def supprimer_reglement(reglement_id:int,db:Session=Depends(get_db),utilisateur:models.User=Depends(auth.get_current_user)):
    reglement=db.query(models.Reglement).join(models.Dette).filter(models.Reglement.id==reglement_id,models.Dette.user_id==utilisateur.id).first()
    if reglement is None: raise HTTPException(status_code=404,detail="Règlement introuvable.")
    db.delete(reglement); db.commit()
@app.get("/api/resume",response_model=schemas.ResumeOut,tags=["Tableau de bord"])
def resume(db:Session=Depends(get_db),utilisateur:models.User=Depends(auth.get_current_user)):
    dettes=db.query(models.Dette).options(joinedload(models.Dette.reglements)).filter(models.Dette.user_id==utilisateur.id).all(); par_devise={}; ouvertes=retard=0
    for dette in dettes:
        ligne=par_devise.setdefault(dette.devise,{"a_percevoir":0.0,"a_payer":0.0,"solde":0.0})
        if dette.sens==models.Sens.PRET: ligne["a_percevoir"]+=dette.restant
        else: ligne["a_payer"]+=dette.restant
        if dette.statut!=models.Statut.PAYEE: ouvertes+=1
        if dette.statut==models.Statut.EN_RETARD: retard+=1
    for ligne in par_devise.values(): ligne["a_percevoir"]=round(ligne["a_percevoir"],2); ligne["a_payer"]=round(ligne["a_payer"],2); ligne["solde"]=round(ligne["a_percevoir"]-ligne["a_payer"],2)
    nb_contacts=db.query(func.count(models.Contact.id)).filter(models.Contact.user_id==utilisateur.id).scalar() or 0
    return {"par_devise":par_devise,"nb_contacts":nb_contacts,"nb_dettes_ouvertes":ouvertes,"nb_en_retard":retard}
@app.get("/api/backup/json",tags=["Sauvegarde"])
def sauvegarde_json(db:Session=Depends(get_db),utilisateur:models.User=Depends(auth.get_current_user)):
    contacts=db.query(models.Contact).options(joinedload(models.Contact.dettes).joinedload(models.Dette.reglements)).filter(models.Contact.user_id==utilisateur.id).order_by(models.Contact.nom.asc()).all()
    donnees={"version_export":1,"genere_le":date.today().isoformat(),"compte":utilisateur.email,"contacts":[{"id":c.id,"nom":c.nom,"telephone":c.telephone,"note":c.note,"soldes":c.soldes,"dettes":[{"id":d.id,"sens":d.sens.value,"montant":d.montant,"devise":d.devise,"date_operation":d.date_operation.isoformat(),"date_echeance":d.date_echeance.isoformat() if d.date_echeance else None,"note":d.note,"montant_regle":d.montant_regle,"restant":d.restant,"statut":d.statut.value,"reglements":[{"id":r.id,"montant":r.montant,"date_reglement":r.date_reglement.isoformat(),"note":r.note} for r in d.reglements]} for d in c.dettes]} for c in contacts]}
    contenu=json.dumps(donnees,ensure_ascii=False,indent=2); nom=f"sauvegarde-carnet-{date.today().isoformat()}.json"
    return StreamingResponse(io.BytesIO(contenu.encode("utf-8")),media_type="application/json",headers={"Content-Disposition":f'attachment; filename="{nom}"'})
@app.get("/api/admin/backup",tags=["Sauvegarde"])
def sauvegarde_base_complete(utilisateur:models.User=Depends(auth.get_admin_actuel)):
    chemin_source=Path(DATABASE_URL.removeprefix("sqlite:///"))
    if not chemin_source.is_file(): raise HTTPException(status_code=404,detail="Fichier de base introuvable.")
    fichier_temp=tempfile.NamedTemporaryFile(suffix=".sqlite",delete=False); fichier_temp.close(); shutil.copyfile(chemin_source,fichier_temp.name)
    nom=f"carnet-dettes-base-{date.today().isoformat()}.sqlite"
    return FileResponse(fichier_temp.name,media_type="application/vnd.sqlite3",filename=nom,background=BackgroundTask(lambda:Path(fichier_temp.name).unlink(missing_ok=True)))
DOSSIER_FRONT=Path(__file__).resolve().parent.parent/"frontend"
if DOSSIER_FRONT.is_dir(): app.mount("/",StaticFiles(directory=DOSSIER_FRONT,html=True),name="frontend")
