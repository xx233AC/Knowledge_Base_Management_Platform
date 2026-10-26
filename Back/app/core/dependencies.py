from typing import Annotated
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.errors import require
from app.services.identity import IdentityService, Identity

bearer = HTTPBearer(auto_error=False)


def database(request: Request):
    with request.app.state.session_factory() as db:
        yield db
        db.commit()


DB = Annotated[Session, Depends(database)]


def identity(request: Request, db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    require(credentials is not None and credentials.scheme.lower() == 'bearer', '请先登录', 401)
    return IdentityService(db, request.app.state.settings).resolve(credentials.credentials)


Actor = Annotated[Identity, Depends(identity)]
