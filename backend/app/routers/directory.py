"""Public workplace search used at sign-up: the national directory plus registered workplaces."""

from fastapi import APIRouter, Query

from .. import directory
from ..schemas import DirectoryHit
from ..security import DB

router = APIRouter(tags=["directory"])


@router.get("/directory/search", response_model=list[DirectoryHit])
def search(db: DB, q: str = Query(min_length=2, max_length=80), state: str | None = None, limit: int = Query(default=20, ge=1, le=50)):
    return directory.search(db, q, state, limit)


@router.get("/directory/states")
def states(db: DB):
    return directory.states(db)
