"""Authentification : hachage des mots de passe et jetons JWT."""

import os
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import models
import schemas
from database import get_db
ALGORITHME = "HS256"
DUREE_TOKEN_MINUTES = 60 * 24
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    warnings.warn("SECRET_KEY absente de l'environnement : utilisation d'une clé aléatoire temporaire.", RuntimeWarning, stacklevel=1)
    SECRET_KEY = secrets.token_hex(32)
contexte_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
schema_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
router = APIRouter(prefix="/api/auth", tags=["Authentification"])
def hacher_mot_de_passe(mot_de_passe: str) -> str: return contexte_pwd.hash(mot_de_passe)
def verifier_mot_de_passe(mot_de_passe: str, hache: str) -> bool: return contexte_pwd.verify(mot_de_passe, hache)
def creer_token(user_id: int) -> str:
    expiration=datetime.now(timezone.utc)+timedelta(minutes=DUREE_TOKEN_MINUTES); payload={"sub":str(user_id),"exp":expiration}; return jwt.encode(payload,SECRET_KEY,algorithm=ALGORITHME)
def get_current_user(token:str=Depends(schema_oauth2),db:Session=Depends(get_db))->models.User:
    erreur=HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Identifiants invalides ou expirés.",headers={"WWW-Authenticate":"Bearer"})
    try:
        payload=jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHME]); id_brut=payload.get("sub")
        if id_brut is None: raise erreur
    except JWTError: raise erreur
    utilisateur=db.get(models.User,int(id_brut))
    if utilisateur is None: raise erreur
    return utilisateur
def get_admin_actuel(utilisateur:models.User=Depends(get_current_user))->models.User:
    if not utilisateur.est_admin: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Cette opération est réservée aux administrateurs.")
    return utilisateur
@router.post("/register",response_model=schemas.UserOut,status_code=status.HTTP_201_CREATED,summary="Créer un compte")
def inscription(payload:schemas.UserCreate,db:Session=Depends(get_db)):
    email=payload.email.lower(); existe=db.query(models.User).filter(models.User.email==email).first()
    if existe: raise HTTPException(status_code=400,detail="Un compte existe déjà avec cet e-mail.")
    utilisateur=models.User(email=email,mot_de_passe_hache=hacher_mot_de_passe(payload.mot_de_passe)); db.add(utilisateur); db.commit(); db.refresh(utilisateur); return utilisateur
@router.post("/login",response_model=schemas.Token,summary="Se connecter")
def connexion(formulaire:OAuth2PasswordRequestForm=Depends(),db:Session=Depends(get_db)):
    email=formulaire.username.lower(); utilisateur=db.query(models.User).filter(models.User.email==email).first(); identifiants_invalides=HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="E-mail ou mot de passe incorrect.")
    if utilisateur is None or not verifier_mot_de_passe(formulaire.password,utilisateur.mot_de_passe_hache): raise identifiants_invalides
    return schemas.Token(access_token=creer_token(utilisateur.id))
