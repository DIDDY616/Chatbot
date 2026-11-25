"""Reuniones de Teams (conexión directa como invitado)."""
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import profiles, teams
from .security import require_admin

router = APIRouter(tags=["reuniones"], dependencies=[Depends(require_admin)])


class MeetingRequest(BaseModel):
    url: str
    profile: str = profiles.DEFAULT_PROFILE
    name: str | None = None  # nombre con el que aparece en la reunión; por omisión, el del asistente


def is_teams_link(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return url.startswith("https://") and any(host == h or host.endswith(f".{h}") for h in teams.TEAMS_HOSTS)


@router.post("/meeting/join")
def join_meeting(req: MeetingRequest):
    """El asistente entra a la reunión del enlace con su avatar y su voz."""
    url = req.url.strip()
    if not is_teams_link(url):
        raise HTTPException(400, "El enlace no parece de una reunión de Teams.")
    try:
        profile = profiles.get(req.profile)
        return teams.join(url, req.profile, (req.name or "").strip() or profile.name)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/meeting/leave")
def leave_meeting():
    return teams.leave()


@router.get("/meeting")
def meeting_status():
    return teams.status()
