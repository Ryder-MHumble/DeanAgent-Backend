from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db.pool import get_pool
from app.schemas.publication import (
    CandidateConfirmRequest,
    CandidateRejectRequest,
    PublicationBulkImportRequest,
    PublicationBulkImportResponse,
    PublicationCandidateConfirmResponse,
    PublicationCandidateListResponse,
    PublicationCandidateRejectResponse,
    PublicationListResponse,
    PublicationOwnerPatchRequest,
    PublicationWriteRequest,
    PublicationWriteResponse,
)
from app.services import publication_service

router = APIRouter()


@router.get(
    "/publications",
    response_model=PublicationListResponse,
    summary="正式论文列表",
)
async def get_publications(
    owner_type: str = Query(...),
    owner_id: str = Query(...),
) -> PublicationListResponse:
    items = await publication_service.list_publications(
        get_pool(),
        owner_type=owner_type,
        owner_id=owner_id,
    )
    return PublicationListResponse(items=items, total=len(items))


@router.post(
    "/publications/manual",
    response_model=PublicationWriteResponse,
    status_code=201,
    summary="手动上传正式论文",
)
async def create_manual_publication(body: PublicationWriteRequest) -> PublicationWriteResponse:
    try:
        result = await publication_service.create_formal_publication(
            get_pool(),
            owner_type=body.owner_type,
            owner_id=body.owner_id,
            title=body.title,
            doi=body.doi,
            arxiv_id=body.arxiv_id,
            abstract=body.abstract,
            publication_date=body.publication_date,
            authors=body.authors,
            affiliations=body.affiliations,
            project_group_name=body.project_group_name,
            source_type=body.source_type or "manual_upload",
            source_details=body.source_details,
            compliance_details=body.compliance_details,
            confirmed_by=body.confirmed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PublicationWriteResponse(**result)


@router.post(
    "/publications/bulk-import",
    response_model=PublicationBulkImportResponse,
    status_code=201,
    summary="批量导入正式论文",
)
async def bulk_import_publications(body: PublicationBulkImportRequest) -> PublicationBulkImportResponse:
    items: list[PublicationWriteResponse] = []
    for payload in body.items:
        try:
            result = await publication_service.create_formal_publication(
                get_pool(),
                owner_type=payload.owner_type,
                owner_id=payload.owner_id,
                title=payload.title,
                doi=payload.doi,
                arxiv_id=payload.arxiv_id,
                abstract=payload.abstract,
                publication_date=payload.publication_date,
                authors=payload.authors,
                affiliations=payload.affiliations,
                project_group_name=payload.project_group_name,
                source_type=payload.source_type or "bulk_import",
                source_details=payload.source_details,
                compliance_details=payload.compliance_details,
                confirmed_by=payload.confirmed_by,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        items.append(PublicationWriteResponse(**result))
    return PublicationBulkImportResponse(items=items, total=len(items))


@router.patch(
    "/publication-owners/{owner_link_id}",
    response_model=PublicationWriteResponse,
    summary="更新 owner 关系与论文客观字段",
)
async def patch_publication_owner(
    owner_link_id: str,
    body: PublicationOwnerPatchRequest,
) -> PublicationWriteResponse:
    try:
        result = await publication_service.update_owner_publication(
            get_pool(),
            owner_link_id=owner_link_id,
            title=body.title,
            doi=body.doi,
            arxiv_id=body.arxiv_id,
            abstract=body.abstract,
            publication_date=body.publication_date,
            authors=body.authors,
            affiliations=body.affiliations,
            project_group_name=body.project_group_name,
            source_type=body.source_type,
            source_details=body.source_details,
            compliance_details=body.compliance_details,
            confirmed_by=body.confirmed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="publication owner not found")
    return PublicationWriteResponse(**result)


@router.get(
    "/publication-candidates",
    response_model=PublicationCandidateListResponse,
    summary="候选论文列表",
)
async def get_publication_candidates(
    owner_type: str = Query(...),
    owner_id: str = Query(...),
    review_status: str | None = Query(None),
) -> PublicationCandidateListResponse:
    items = await publication_service.list_candidates(
        get_pool(),
        owner_type=owner_type,
        owner_id=owner_id,
        review_status=review_status,
    )
    return PublicationCandidateListResponse(items=items, total=len(items))


@router.post(
    "/publication-candidates/{candidate_id}/confirm",
    response_model=PublicationCandidateConfirmResponse,
    summary="确认候选论文",
)
async def confirm_publication_candidate(
    candidate_id: str,
    body: CandidateConfirmRequest,
) -> PublicationCandidateConfirmResponse:
    result = await publication_service.confirm_candidate(
        get_pool(),
        candidate_id=candidate_id,
        confirmed_by=body.confirmed_by,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return PublicationCandidateConfirmResponse(**result)


@router.post(
    "/publication-candidates/{candidate_id}/reject",
    response_model=PublicationCandidateRejectResponse,
    summary="拒绝候选论文",
)
async def reject_publication_candidate(
    candidate_id: str,
    body: CandidateRejectRequest,
) -> PublicationCandidateRejectResponse:
    ok = await publication_service.reject_candidate(
        get_pool(),
        candidate_id=candidate_id,
        rejected_by=body.rejected_by,
        note=body.note,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="candidate not found")
    return PublicationCandidateRejectResponse(status="rejected", candidate_id=candidate_id)
