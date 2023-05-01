"""Backend service for Clearance Assignment functionality"""

from clearance_service.crud.assignments import router as assignments_router
from clearance_service.crud.audit import router as audit_router
from clearance_service.crud.clearances import router as clearances_router
from clearance_service.crud.liaison import router as liaison_router
from clearance_service.crud.personnel import router as personnel_router
from clearance_service.models.scheduler_framework import ServiceScheduler
from clearance_service.util.ccure_api import CcureApi
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

DESCRIPTION = """Backend service for Clearance Assignment functionality"""
VERSION = "2023-04-21"


def create_app():
    """Set up a FastAPI application instance"""
    fastapi_app = FastAPI(title="Clearance Service", description=DESCRIPTION, version=VERSION)

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return fastapi_app


app = create_app()

app.include_router(personnel_router, prefix="/personnel")
app.include_router(clearances_router, prefix="/clearances")
app.include_router(assignments_router, prefix="/assignments")
app.include_router(liaison_router, prefix="/liaison")
app.include_router(audit_router, prefix="/audit")


@app.get("/", response_class=HTMLResponse)
def default(request: Request):
    """Default landing page, link to documentation"""
    base_url = str(request.url)
    docs_url = base_url + "docs"
    return f"""
    <h3>Clearance Service</h3>
    Go to <a href={docs_url}><code>/docs</code></a> in your browser
    to see the documentation.
    """


@app.on_event("startup")
def startup_db_client():
    """Start the scheduler"""
    scheduler = ServiceScheduler()
    scheduler.start_scheduler()
    print("Started scheduler")


@app.on_event("shutdown")
def logout_ccure_session():
    """Log out of the CCure session"""
    response = CcureApi.logout()
    if response.get("success"):
        print("Ending CCure session")
