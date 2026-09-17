"""Modèles de données : utilisateurs, contacts, dettes et règlements."""

import enum
from datetime import date, datetime
from sqlalchemy import Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    mot_de_passe_hache = Column(String(255), nullable=False)
    est_admin = Column(Boolean, default=False, nullable=False)
    cree_le = Column(DateTime, default=datetime.utcnow, nullable=False)
    contacts = relationship("Contact", back_populates="proprietaire", cascade="all, delete-orphan", passive_deletes=True)

class Sens(str, enum.Enum):
    PRET = "PRET"
    EMPRUNT = "EMPRUNT"

class Statut(str, enum.Enum):
    NON_PAYEE = "NON_PAYEE"
    PARTIELLE = "PARTIELLE"
    EN_RETARD = "EN_RETARD"
    PAYEE = "PAYEE"

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    nom = Column(String(120), nullable=False, index=True)
    telephone = Column(String(40), nullable=True)
    note = Column(Text, nullable=True)
    cree_le = Column(DateTime, default=datetime.utcnow, nullable=False)
    proprietaire = relationship("User", back_populates="contacts")
    dettes = relationship("Dette", back_populates="contact", cascade="all, delete-orphan", passive_deletes=True)
    @property
    def soldes(self) -> dict:
        totaux: dict[str, dict[str, float]] = {}
        for dette in self.dettes:
            ligne = totaux.setdefault(dette.devise, {"a_percevoir": 0.0, "a_payer": 0.0, "solde": 0.0})
            if dette.sens == Sens.PRET:
                ligne["a_percevoir"] += dette.restant
            else:
                ligne["a_payer"] += dette.restant
            ligne["solde"] = round(ligne["a_percevoir"] - ligne["a_payer"], 2)
            ligne["a_percevoir"] = round(ligne["a_percevoir"], 2)
            ligne["a_payer"] = round(ligne["a_payer"], 2)
        return totaux

class Dette(Base):
    __tablename__ = "dettes"
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sens = Column(Enum(Sens), nullable=False, index=True)
    montant = Column(Float, nullable=False)
    devise = Column(String(8), nullable=False, default="EUR")
    date_operation = Column(Date, nullable=False, default=date.today)
    date_echeance = Column(Date, nullable=True)
    note = Column(Text, nullable=True)
    cree_le = Column(DateTime, default=datetime.utcnow, nullable=False)
    contact = relationship("Contact", back_populates="dettes")
    reglements = relationship("Reglement", back_populates="dette", cascade="all, delete-orphan", passive_deletes=True, order_by="Reglement.date_reglement")
    @property
    def montant_regle(self) -> float:
        return round(sum(r.montant for r in self.reglements), 2)
    @property
    def restant(self) -> float:
        return round(max(self.montant - self.montant_regle, 0.0), 2)
    @property
    def statut(self) -> Statut:
        if self.restant <= 0.004: return Statut.PAYEE
        if self.date_echeance and self.date_echeance < date.today(): return Statut.EN_RETARD
        if self.montant_regle > 0: return Statut.PARTIELLE
        return Statut.NON_PAYEE
    @property
    def jours_restants(self) -> int | None:
        if not self.date_echeance or self.statut == Statut.PAYEE: return None
        return (self.date_echeance - date.today()).days

class Reglement(Base):
    __tablename__ = "reglements"
    id = Column(Integer, primary_key=True, index=True)
    dette_id = Column(Integer, ForeignKey("dettes.id", ondelete="CASCADE"), nullable=False, index=True)
    montant = Column(Float, nullable=False)
    date_reglement = Column(Date, nullable=False, default=date.today)
    note = Column(Text, nullable=True)
    cree_le = Column(DateTime, default=datetime.utcnow, nullable=False)
    dette = relationship("Dette", back_populates="reglements")
