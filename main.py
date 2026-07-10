"""Backend service for Clearance Assignment functionality"""
import os

from clearance_service.crud.assignments import router as assignments_router
from clearance_service.crud.audit import router as audit_router
from clearance_service.crud.clearances import router as clearances_router
from clearance_service.crud.doors import router as door_router
from clearance_service.crud.liaison import router as liaison_router
from clearance_service.crud.personnel import router as personnel_router
from clearance_service.crud.reports import router as reports_router
from clearance_service.crud.spaces import router as spaces_router
from clearance_service.crud.space_schedules import router as space_schedule_router
from clearance_service.models import acs
from clearance_service.util.handle_requests import RequestException
from clearance_service.util.scheduler_framework import ServiceScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sat.logs import SATLogger
from prometheus_fastapi_instrumentator import Instrumentator

logger = SATLogger(__name__)

DESCRIPTION = """Backend service supporting the Clearance UI"""
VERSION = "2023-06-04"


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
    Instrumentator().instrument(fastapi_app).expose(fastapi_app)

    return fastapi_app


app = create_app()

app.include_router(personnel_router, prefix="/personnel")
app.include_router(clearances_router, prefix="/clearances")
app.include_router(door_router, prefix="/door")
app.include_router(assignments_router, prefix="/assignments")
app.include_router(liaison_router, prefix="/liaison")
app.include_router(audit_router, prefix="/audit")
app.include_router(reports_router, prefix="/reports")
app.include_router(spaces_router, prefix="/spaces")
app.include_router(space_schedule_router, prefix="/space-schedules")


@app.get("/", response_class=HTMLResponse)
def default(request: Request):
    """Default landing page, link to documentation"""
    base_url = str(request.url)
    docs_url = base_url + "docs"
    return f"""
    <h3>Clearance Service</h3>
    <a href={docs_url}><code>Click here</code></a> for API documentation
    """


@app.on_event("startup")
def startup_db_client():
    """Start the scheduler"""
    if os.getenv("DEVELOPMENT"):
        logger.info("DEVELOPMENT mode, not starting scheduler")
        return
    scheduler = ServiceScheduler()
    scheduler.start_scheduler()
    logger.info("Scheduler started")


@app.on_event("shutdown")
def logout_acs_session():
    try:
        logger.info("Ending ACS session")
        acs.connection.logout()
    except RequestException as e:
        logger.error(f"{e}")
