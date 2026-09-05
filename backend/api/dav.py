import logging
from html import escape as escape_xml_text

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from db.session import get_db
from services.webdav_service import webdav_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dav", tags=["dav"])

IMPLEMENTED_DAV_METHODS = ("OPTIONS", "PROPFIND")
_DAV_AUTHORIZATION_PATH_MAX_CHARACTERS = 8192
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_DAV_STRUCTURAL_OCTETS = frozenset(
    {*range(0x20), 0x2E, 0x2F, 0x5C, 0x7F}
)


def _residual_percent_octet(path: str, percent_index: int) -> int | None:
    """Return the octet exposed by another decode, following nested ``%25``."""

    cursor = percent_index + 1
    while cursor + 1 < len(path):
        pair = path[cursor : cursor + 2]
        if pair[0] not in _HEX_DIGITS or pair[1] not in _HEX_DIGITS:
            return None
        octet = int(pair, 16)
        if octet != 0x25:
            return octet
        cursor += 2
    return None


def _has_ambiguous_percent_encoding(path: str) -> bool:
    """Detect residual encodings that another decode would make structural."""

    for index, character in enumerate(path):
        if character != "%":
            continue
        octet = _residual_percent_octet(path, index)
        if octet in _DAV_STRUCTURAL_OCTETS:
            return True
    return False


def _normalize_dav_authorization_path(path: str) -> str:
    """Validate the framework-decoded DAV path without decoding it again.

    ASGI routing has already decoded the request-target path once. Authorization
    therefore treats residual percent text as data unless another decode would
    introduce a traversal dot, separator, backslash, or control octet. Literal
    backslashes are normalized to separators for owner/traversal checks.
    """

    if len(path) > _DAV_AUTHORIZATION_PATH_MAX_CHARACTERS:
        raise HTTPException(
            status_code=414,
            detail="DAV path exceeds authorization length limit",
        )
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in path):
        raise HTTPException(
            status_code=400,
            detail="DAV path contains control characters",
        )

    normalized_path = path.replace("\\", "/")
    if _has_ambiguous_percent_encoding(normalized_path):
        raise HTTPException(
            status_code=400,
            detail="DAV path contains ambiguous percent encoding",
        )
    return normalized_path


def _dav_path_owner_user_id(path: str) -> str | None:
    path = _normalize_dav_authorization_path(path)
    if any(segment in {".", ".."} for segment in path.split("/")):
        return None
    normalized_path = path.strip("/")
    if not normalized_path:
        return None
    owner_user_id, _, _ = normalized_path.partition("/")
    return owner_user_id or None


def _ensure_dav_owner_scope(path: str, auth_context: AuthContext) -> None:
    owner_user_id = _dav_path_owner_user_id(path)
    if owner_user_id is None:
        raise HTTPException(
            status_code=403,
            detail="DAV path must include an owner user",
        )
    if owner_user_id == auth_context.user_id:
        return
    raise HTTPException(
        status_code=403,
        detail="DAV path belongs to a different user",
    )


def _dav_path_segments(path: str) -> list[str]:
    return [segment for segment in path.strip("/").split("/") if segment]


def _dav_multistatus_xml(responses: list[str]) -> str:
    response_xml = "\n".join(responses)
    if response_xml:
        response_xml = f"\n{response_xml}\n"
    return f"""<?xml version="1.0" encoding="utf-8" ?>
<D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">{response_xml}</D:multistatus>"""


def _dav_response_xml(
    *,
    href: str,
    display_name: str,
    is_collection: bool = True,
) -> str:
    resourcetype = "<D:collection/>" if is_collection else ""
    escaped_href = escape_xml_text(href)
    escaped_display_name = escape_xml_text(display_name)
    return f"""  <D:response>
    <D:href>{escaped_href}</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype>{resourcetype}</D:resourcetype>
        <D:displayname>{escaped_display_name}</D:displayname>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>"""


def _dav_xml_response(responses: list[str]) -> Response:
    return Response(
        content=_dav_multistatus_xml(responses),
        media_type="application/xml",
        status_code=207,
    )


def _dav_depth(request: Request) -> str:
    depth = request.headers.get("Depth", "1").strip().lower()
    if depth == "0":
        return "0"
    return "1"


def _project_folder_response(path_owner_user_id: str, folder: dict) -> str:
    folder_uid = str(folder["folder_uid"])
    project_name = str(folder["project_name"])
    return _dav_response_xml(
        href=f"/api/dav/{path_owner_user_id}/projects/{folder_uid}",
        display_name=project_name,
        is_collection=True,
    )


async def _handle_project_propfind(
    *,
    request: Request,
    path: str,
    auth_context: AuthContext,
    db: AsyncSession,
) -> Response:
    segments = _dav_path_segments(path)
    if len(segments) < 2 or segments[1] != "projects":
        raise HTTPException(status_code=404, detail="DAV collection not found")

    path_owner_user_id = segments[0]
    depth = _dav_depth(request)
    folder_uid = segments[2] if len(segments) == 3 else None
    if len(segments) > 3:
        raise HTTPException(status_code=404, detail="DAV project folder not found")

    if folder_uid is None and depth == "0":
        return _dav_xml_response(
            [
                _dav_response_xml(
                    href=f"/api/dav/{path_owner_user_id}/projects/",
                    display_name="projects",
                    is_collection=True,
                )
            ]
        )

    folders = await webdav_service.get_project_folders_from_db(
        db,
        auth_context.user_id,
        auth_context.organization_id,
        folder_uid=folder_uid,
    )

    if folder_uid is None:
        return _dav_xml_response(
            [_project_folder_response(path_owner_user_id, folder) for folder in folders]
        )

    if folders:
        return _dav_xml_response(
            [_project_folder_response(path_owner_user_id, folder) for folder in folders]
        )

    raise HTTPException(status_code=404, detail="DAV project folder not found")


@router.api_route(
    "/{path:path}",
    methods=list(IMPLEMENTED_DAV_METHODS),
)
async def dav_handler(
    request: Request,
    path: str,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serve only the authenticated DAV capabilities implemented in production.

    Project collection discovery is available through ``PROPFIND``. Unsupported
    writeback and richer DAV verbs are deliberately not registered, so clients
    receive ``405 Method Not Allowed`` instead of a misleading advertised
    capability that can only return ``501 Not Implemented``.
    """
    normalized_path = _normalize_dav_authorization_path(path)
    _ensure_dav_owner_scope(normalized_path, auth_context)
    safe_path = repr(normalized_path)[1:-1]
    logger.info("DAV Request: %s /%s", request.method, safe_path)

    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "DAV": "1",
                "Allow": ", ".join(IMPLEMENTED_DAV_METHODS),
            },
        )

    return await _handle_project_propfind(
        request=request,
        path=normalized_path,
        auth_context=auth_context,
        db=db,
    )
