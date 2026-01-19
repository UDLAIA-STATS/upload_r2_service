from typing import Any
from rest_framework.response import Response

def success_response(message: str, data: Any, status) -> Response:
    return Response(
        data={
            "mensaje": message,
            "data": data,
            "status": status
        },
        status=status
    )

def error_response(message: str, data: Any, status) -> Response:
    return Response(
        data={
            "error": message,
            "data": data,
            "status": status
        },
        status=status
    )

def pagination_response(
        data: Any,
        page: int,
        offset: int,
        pages: int,
        total_items: int,
        status) -> Response:
    return Response(
        data={
            "count": total_items,
            "page": page,
            "offset": offset,
            "pages": pages,
            "results": data
        },
        status=status
    )