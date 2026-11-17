from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.schemas import AnalysisResponse, LinkAnalysisRequest
from app.services.analysis_service import analyze
from app.utils.validators import AppError

app = FastAPI(title="AI Link Analysis API")


@app.exception_handler(AppError)
async def app_error(_: Request, e: AppError):
    return JSONResponse({"success": False, "error": e.message}, status_code=e.status_code)


@app.post("/link-analysis", response_model=AnalysisResponse)
async def link_analysis(req: LinkAnalysisRequest):
    return await analyze(str(req.url))
