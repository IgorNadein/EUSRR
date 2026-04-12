"""Read-only endpoints для directory identity данных."""

from __future__ import annotations

import logging

from employees.ldap.errors import DirectoryDbError, DirectoryLdapError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import DirectoryLoginResponseSerializer
from .services import resolve_directory_login

logger = logging.getLogger(__name__)


class DirectoryMeLoginAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            result = resolve_directory_login(request.user, force_refresh=False)
        except (DirectoryLdapError, DirectoryDbError) as exc:
            logger.error("Directory login lookup failed: %s", exc, exc_info=True)
            return Response(
                {"detail": str(exc), "error": "directory_lookup_failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = DirectoryLoginResponseSerializer(result)
        return Response(serializer.data)


class DirectoryMeLoginRefreshAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            result = resolve_directory_login(request.user, force_refresh=True)
        except (DirectoryLdapError, DirectoryDbError) as exc:
            logger.error(
                "Directory login refresh failed: %s", exc, exc_info=True
            )
            return Response(
                {"detail": str(exc), "error": "directory_refresh_failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = DirectoryLoginResponseSerializer(result)
        return Response(serializer.data)

