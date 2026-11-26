"""Account-bound notes for the technical interview cheatsheet."""
from fastapi import APIRouter, Depends, Response

from app.auth.dependencies import get_current_user, has_account_bound_token
from app.models import User
from app.services import private_hr

router = APIRouter()


@router.get("/cheatsheets/python-ai-interview/answers", response_model=private_hr.TechnicalAnswers)
def get_private_interview_answers(
    response: Response,
    user: User = Depends(get_current_user),
    account_bound: bool = Depends(has_account_bound_token),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    if not account_bound:
        return {}
    return private_hr.get_technical_answers(user.id, user.email, user.created_at)


@router.get("/cheatsheets/python-ai-interview/agent-guide", response_model=private_hr.AgentGuideSections)
def get_private_agent_guide(
    response: Response,
    user: User = Depends(get_current_user),
    account_bound: bool = Depends(has_account_bound_token),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    if not account_bound:
        return []
    return private_hr.get_agent_guide(user.id, user.email, user.created_at)


@router.get("/cheatsheets/my-resume", response_model=private_hr.ResumeSections, response_model_exclude_none=True)
def get_private_resume(
    response: Response,
    user: User = Depends(get_current_user),
    account_bound: bool = Depends(has_account_bound_token),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    if not account_bound:
        return []
    return private_hr.get_resume(user.id, user.email, user.created_at)



@router.get("/cheatsheets/my-resume/pdf", response_class=Response)
def download_private_resume(
    user: User = Depends(get_current_user),
    account_bound: bool = Depends(has_account_bound_token),
):
    headers = {"Cache-Control": "private, no-store", "Vary": "Authorization"}
    content = private_hr.get_resume_pdf(user.id, user.email, user.created_at) if account_bound else None
    if content is None:
        return Response(status_code=404, headers=headers)
    headers["Content-Disposition"] = 'attachment; filename="my-resume-cheatsheet.pdf"'
    headers["X-Content-Type-Options"] = "nosniff"
    return Response(content=content, media_type="application/pdf", headers=headers)
