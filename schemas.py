"""Schémas Pydantic : validation des entrées et forme des réponses JSON."""

from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from models import Sens, Statut
ORM = ConfigDict(from_attributes=True)
class UserCreate(BaseModel):
    email: EmailStr
    mot_de_passe: str = Field(min_length=8, max_length=128)
class UserOut(BaseModel):
    model_config = ORM
    id: int
    email: EmailStr
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
class ContactBase(BaseModel):
    nom: str = Field(min_length=1, max_length=120)
    telephone: Optional[str] = Field(default=None, max_length=40)
    note: Optional[str] = None
    @field_validator("nom")
    @classmethod
    def nom_non_vide(cls, v: str) -> str:
        v = v.strip()
        if not v: raise ValueError("Le nom ne peut pas être vide.")
        return v
class ContactCreate(ContactBase): pass
class ContactUpdate(BaseModel):
    nom: Optional[str] = Field(default=None, min_length=1, max_length=120)
    telephone: Optional[str] = Field(default=None, max_length=40)
    note: Optional[str] = None
class SoldeDevise(BaseModel):
    a_percevoir: float
    a_payer: float
    solde: float
class ContactOut(ContactBase):
    model_config = ORM
    id: int
    soldes: dict[str, SoldeDevise] = {}
class ReglementCreate(BaseModel):
    montant: float = Field(gt=0, description="Doit être strictement positif.")
    date_reglement: date = Field(default_factory=date.today)
    note: Optional[str] = None
class ReglementOut(BaseModel):
    model_config = ORM
    id: int
    dette_id: int
    montant: float
    date_reglement: date
    note: Optional[str] = None
class DetteBase(BaseModel):
    contact_id: int
    sens: Sens
    montant: float = Field(gt=0)
    devise: str = Field(default="EUR", min_length=1, max_length=8)
    date_operation: date = Field(default_factory=date.today)
    date_echeance: Optional[date] = None
    note: Optional[str] = None
    @field_validator("devise")
    @classmethod
    def devise_majuscule(cls, v: str) -> str: return v.strip().upper()
class DetteCreate(DetteBase): pass
class DetteUpdate(BaseModel):
    contact_id: Optional[int] = None
    sens: Optional[Sens] = None
    montant: Optional[float] = Field(default=None, gt=0)
    devise: Optional[str] = Field(default=None, min_length=1, max_length=8)
    date_operation: Optional[date] = None
    date_echeance: Optional[date] = None
    note: Optional[str] = None
class ContactMini(BaseModel):
    model_config = ORM
    id: int
    nom: str
    telephone: Optional[str] = None
class DetteOut(BaseModel):
    model_config = ORM
    id: int
    sens: Sens
    montant: float
    devise: str
    date_operation: date
    date_echeance: Optional[date] = None
    note: Optional[str] = None
    contact: ContactMini
    reglements: list[ReglementOut] = []
    montant_regle: float
    restant: float
    statut: Statut
    jours_restants: Optional[int] = None
class ResumeOut(BaseModel):
    par_devise: dict[str, SoldeDevise]
    nb_contacts: int
    nb_dettes_ouvertes: int
    nb_en_retard: int
