"""Asistentes (perfiles) y personajes 3D."""
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from .. import avatars, profiles
from .security import require_admin

router = APIRouter(tags=["asistentes"])
admin = [Depends(require_admin)]


@router.get("/profiles")
def list_profiles() -> dict[str, profiles.Profile]:
    return profiles.load()


@router.put("/profiles/{profile_id}", dependencies=admin)
def save_profile(profile_id: str, profile: profiles.Profile):
    try:
        profiles.save(profile_id, profile)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}


@router.delete("/profiles/{profile_id}", dependencies=admin)
def delete_profile(profile_id: str):
    try:
        profiles.delete(profile_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}


@router.get("/avatars")
def list_avatars():
    return avatars.list_all()


@router.post("/avatars", dependencies=admin)
def upload_avatar(file: UploadFile, name: str = Form(...), body: str = Form("F"), license: str = Form("")):
    """Agrega un personaje propio (.glb compatible con TalkingHead)."""
    try:
        return avatars.add(name, file.file.read(), body, license)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/avatars/{avatar_id}", dependencies=admin)
def delete_avatar(avatar_id: str):
    try:
        avatars.delete(avatar_id)
    except KeyError as e:
        raise HTTPException(404, e.args[0]) from e
    return {"ok": True}
