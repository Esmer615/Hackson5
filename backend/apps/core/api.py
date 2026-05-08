from ninja import Router

router = Router(tags=["core"])


@router.get("/health", summary="Health check")
def health_check(request):
    return {"status": "ok"}
