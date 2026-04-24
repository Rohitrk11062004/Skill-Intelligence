"""app/api/v1/router.py"""
from fastapi import APIRouter
from app.api.v1.endpoints import (
	admin,
	assessments,
	auth,
	catalog,
	content,
	dashboard,
	gaps,
	learning,
	resume,
	roles,
	week_assessments,
	users,
	features,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(resume.router)
api_router.include_router(roles.router)
api_router.include_router(gaps.router)
api_router.include_router(learning.router)
api_router.include_router(dashboard.router)
api_router.include_router(admin.router)
api_router.include_router(catalog.router)
api_router.include_router(content.router)
api_router.include_router(content.public_router)
api_router.include_router(assessments.router)
api_router.include_router(assessments.admin_router)
api_router.include_router(week_assessments.router)
api_router.include_router(users.router)
api_router.include_router(features.reports_router)
api_router.include_router(features.talent_map_router)
