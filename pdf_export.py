"""Export PDF — relevé de compte d'un contact, construit avec ReportLab."""
import html, io
from datetime import date, datetime
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, joinedload
import models
from auth import get_current_user
from database import get_db
from utils_export import LIBELLE_SENS, LIBELLE_STATUT, nom_fichier_sur
router=APIRouter(prefix="/api",tags=["Export"])
ENCRE=colors.HexColor("#14212E"); ARDOISE=colors.HexColor("#5B6B7C"); LIGNE=colors.HexColor("#D7DDE4"); ZEBRURE=colors.HexColor("#F5F6F8")
def _e(texte)->str: return html.escape(str(texte or ""),quote=False)
def _montant(valeur:float)->str: return f"{valeur:,.2f}".replace(",","\u202f").replace(".",",")
def _charger_contact_du_proprietaire(db:Session,contact_id:int,utilisateur:models.User)->models.Contact:
    contact=db.query(models.Contact).options(joinedload(models.Contact.dettes).joinedload(models.Dette.reglements)).filter(models.Contact.id==contact_id,models.Contact.user_id==utilisateur.id).first()
    if contact is None: raise HTTPException(status_code=404,detail="Contact introuvable.")
    return contact
@router.get("/contacts/{contact_id}/export/pdf",response_class=StreamingResponse,summary="Exporter un relevé de compte au format PDF")
def exporter_contact_pdf(contact_id:int,db:Session=Depends(get_db),utilisateur:models.User=Depends(get_current_user)):
    contact=_charger_contact_du_proprietaire(db,contact_id,utilisateur); tampon=io.BytesIO(); doc=SimpleDocTemplate(tampon,pagesize=A4,topMargin=2*cm,bottomMargin=2*cm,leftMargin=2*cm,rightMargin=2*cm,title=f"Relevé — {contact.nom}")
    styles=getSampleStyleSheet(); style_titre=ParagraphStyle("TitreCarnet",parent=styles["Title"],textColor=ENCRE,fontSize=19,leading=23,spaceAfter=2); style_sous_titre=ParagraphStyle("SousTitre",parent=styles["Normal"],textColor=ARDOISE,fontSize=10,leading=14,spaceAfter=18); style_section=ParagraphStyle("EnteteSection",parent=styles["Heading2"],textColor=ENCRE,fontSize=13,spaceBefore=18,spaceAfter=8); style_cellule=ParagraphStyle("Cellule",parent=styles["Normal"],fontSize=8,leading=10); style_note_vide=ParagraphStyle("NoteVide",parent=styles["Normal"],fontSize=9,textColor=ARDOISE)
    histoire=[Paragraph("Carnet de dettes — Relevé de compte",style_titre),Paragraph(f"{_e(contact.nom)} · {_e(contact.telephone or 'Sans téléphone')}<br/>Édité le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",style_sous_titre)]
    dettes=sorted(contact.dettes,key=lambda d:(d.date_operation,d.id)); histoire.append(Paragraph("Opérations",style_section))
    if not dettes: histoire.append(Paragraph("Aucune opération enregistrée pour ce contact.",style_note_vide))
    else:
        lignes=[["Date","Opération","Montant","Réglé","Reste","Statut"]]
        for dette in dettes:
            note=f" — {_e(dette.note)}" if dette.note else ""; lignes.append([dette.date_operation.strftime("%d/%m/%Y"),Paragraph(f"{_e(LIBELLE_SENS[dette.sens])}{note}",style_cellule),f"{_montant(dette.montant)} {dette.devise}",f"{_montant(dette.montant_regle)} {dette.devise}",f"{_montant(dette.restant)} {dette.devise}",LIBELLE_STATUT[dette.statut]])
            for reglement in sorted(dette.reglements,key=lambda r:(r.date_reglement,r.id)): lignes.append([reglement.date_reglement.strftime("%d/%m/%Y"),Paragraph(f"↳ Règlement{(' — '+_e(reglement.note)) if reglement.note else ''}",style_cellule),f"{_montant(reglement.montant)} {dette.devise}","","",""])
        table=Table(lignes,colWidths=[2.2*cm,6.8*cm,2.6*cm,2.6*cm,2.6*cm,2.2*cm],repeatRows=1); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),ENCRE),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8.5),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,ZEBRURE]),("GRID",(0,0),(-1,-1),0.5,LIGNE),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)])); histoire.append(table)
    histoire.append(Paragraph("Solde net par devise",style_section)); soldes=contact.soldes
    if not soldes: histoire.append(Paragraph("Aucun solde à afficher.",style_note_vide))
    else:
        lignes=[["Devise","À percevoir","À payer","Solde net"]]
        for devise,ligne in sorted(soldes.items()): lignes.append([devise,f"{_montant(ligne['a_percevoir'])} {devise}",f"{_montant(ligne['a_payer'])} {devise}",f"{_montant(ligne['solde'])} {devise}"])
        table_soldes=Table(lignes,colWidths=[3*cm,4.5*cm,4.5*cm,4.5*cm]); table_soldes.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),ENCRE),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),0.5,LIGNE),("FONTSIZE",(0,0),(-1,-1),9.5),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)])); histoire.append(table_soldes); histoire.append(Spacer(1,10)); histoire.append(Paragraph("Solde positif : le contact vous doit de l'argent. Solde négatif : vous lui devez de l'argent.",style_note_vide))
    doc.build(histoire); tampon.seek(0); nom=f"releve-{nom_fichier_sur(contact.nom)}-{date.today().isoformat()}.pdf"
    return StreamingResponse(tampon,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{nom}"; filename*=UTF-8\'\'{quote(nom)}'})
