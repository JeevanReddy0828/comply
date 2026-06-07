from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import settings
from app.guard import classifier, service
from app.guard.schemas import GuardRequest, GuardVerdict
from app.ratelimit import RateLimiter

router = APIRouter(prefix="/guard", tags=["guard"])

_limiter = RateLimiter(settings.rate_limit_max, settings.rate_limit_window_seconds)


def _rate_limit(body: GuardRequest, request: Request) -> None:
    key = body.identifier or (request.client.host if request.client else "anonymous")
    allowed, retry_after = _limiter.check(key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


@router.post("/check", response_model=GuardVerdict)
def check(body: GuardRequest, request: Request, _: None = Depends(_rate_limit)) -> GuardVerdict:
    return service.evaluate(body.text)


@router.get("/status")
def guard_status() -> dict:
    return classifier.status()
