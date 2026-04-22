"""
Legacy public email endpoints.

The system transactional mail now lives exclusively behind the auth flows and
the master-admin status/test panel. These endpoints are kept as explicit retired
compatibility shims so old callers get a clear 410.
"""
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/email", tags=["Email"])


def _retired() -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Legacy email endpoints were retired. Use the auth flows or the master-admin email panel.",
    )


@router.post("/verify")
def send_verification(*_args, **_kwargs):
    _retired()


@router.post("/reset")
def send_reset(*_args, **_kwargs):
    _retired()


@router.post("/verify-code")
def verify_code(*_args, **_kwargs):
    _retired()
