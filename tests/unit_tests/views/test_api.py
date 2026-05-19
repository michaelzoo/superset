# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Unit tests for resource-level authorization in superset/views/api.py.

Tests use ``inspect.unwrap`` to call the underlying view logic directly,
bypassing the Flask-AppBuilder permission decorator machinery.
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.exceptions import SupersetSecurityException


def _security_exception() -> SupersetSecurityException:
    return SupersetSecurityException(
        SupersetError(
            message="Access denied",
            error_type=SupersetErrorType.DATASOURCE_SECURITY_ACCESS_ERROR,
            level=ErrorLevel.WARNING,
        )
    )


def _get_view_func(name: str):
    """Return the unwrapped body of an Api view method."""
    from superset.views.api import Api

    return inspect.unwrap(getattr(Api, name))


def _view_self() -> MagicMock:
    """Create a minimal stand-in for an Api view instance."""
    from superset.views.base import BaseSupersetView

    self = MagicMock()
    self.json_response = BaseSupersetView.json_response
    return self


@pytest.fixture
def flask_app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@patch("superset.views.api.update_time_range")
@patch("superset.views.api.security_manager", new_callable=MagicMock)
@patch("superset.views.api.db")
def test_query_form_data_returns_403_when_access_denied(
    mock_db: MagicMock,
    mock_security_manager: MagicMock,
    mock_update_time_range: MagicMock,
    flask_app: Flask,
) -> None:
    """A user without chart access receives a 403 response."""
    mock_slice = MagicMock()
    mock_slice.form_data = {"viz_type": "table", "datasource": "1__table"}
    query_chain = mock_db.session.query.return_value
    query_chain.filter_by.return_value.one_or_none.return_value = mock_slice
    mock_security_manager.raise_for_access.side_effect = _security_exception()

    raw_func = _get_view_func("query_form_data")
    with flask_app.test_request_context("/v1/form_data/?slice_id=42"):
        response = raw_func(_view_self())

    assert response.status_code == 403
    mock_security_manager.raise_for_access.assert_called_once_with(chart=mock_slice)


@patch("superset.views.api.update_time_range")
@patch("superset.views.api.security_manager", new_callable=MagicMock)
@patch("superset.views.api.db")
def test_query_form_data_returns_data_when_access_granted(
    mock_db: MagicMock,
    mock_security_manager: MagicMock,
    mock_update_time_range: MagicMock,
    flask_app: Flask,
) -> None:
    """A user with chart access receives the form_data payload."""
    expected_form_data = {"viz_type": "table", "datasource": "1__table"}
    mock_slice = MagicMock()
    mock_slice.form_data = expected_form_data.copy()
    query_chain = mock_db.session.query.return_value
    query_chain.filter_by.return_value.one_or_none.return_value = mock_slice
    mock_security_manager.raise_for_access.return_value = None

    raw_func = _get_view_func("query_form_data")
    with flask_app.test_request_context("/v1/form_data/?slice_id=42"):
        response = raw_func(_view_self())

    assert response.status_code == 200
    mock_security_manager.raise_for_access.assert_called_once_with(chart=mock_slice)


@patch("superset.views.api.update_time_range")
@patch("superset.views.api.security_manager", new_callable=MagicMock)
@patch("superset.views.api.db")
def test_query_form_data_no_slice_id_returns_empty(
    mock_db: MagicMock,
    mock_security_manager: MagicMock,
    mock_update_time_range: MagicMock,
    flask_app: Flask,
) -> None:
    """When no slice_id is provided, return empty form_data without access check."""
    raw_func = _get_view_func("query_form_data")
    with flask_app.test_request_context("/v1/form_data/"):
        response = raw_func(_view_self())

    assert response.status_code == 200
    mock_security_manager.raise_for_access.assert_not_called()
