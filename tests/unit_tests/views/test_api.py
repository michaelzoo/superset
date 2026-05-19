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
    self = MagicMock()
    self.json_response = MagicMock(return_value="ok")
    return self


# ---------------------------------------------------------------------------
# Api.query_form_data — IDOR fix
# ---------------------------------------------------------------------------


@patch("superset.views.api.update_time_range")
@patch("superset.views.api.security_manager", new_callable=MagicMock)
@patch("superset.views.api.db")
def test_query_form_data_returns_403_when_access_denied(
    mock_db: MagicMock,
    mock_security_manager: MagicMock,
    mock_update_time_range: MagicMock,
    app_context: None,
) -> None:
    """An unauthorised user receives a 403 instead of the chart's form_data."""
    import superset.views.api as api_module

    mock_request = MagicMock()
    mock_request.args.get.return_value = "42"

    mock_slice = MagicMock()
    query_chain = mock_db.session.query.return_value
    query_chain.filter_by.return_value.one_or_none.return_value = mock_slice
    mock_security_manager.raise_for_access.side_effect = _security_exception()

    view = _view_self()
    raw_fn = _get_view_func("query_form_data")

    with patch.object(api_module, "request", mock_request):
        raw_fn(view)

    mock_security_manager.raise_for_access.assert_called_once_with(chart=mock_slice)
    view.json_response.assert_called_once()
    call_args = view.json_response.call_args
    assert call_args[0][0] == {"error": "Access denied"}
    assert call_args[1]["status"] == 403


@patch("superset.views.api.update_time_range")
@patch("superset.views.api.security_manager", new_callable=MagicMock)
@patch("superset.views.api.db")
def test_query_form_data_returns_data_when_authorised(
    mock_db: MagicMock,
    mock_security_manager: MagicMock,
    mock_update_time_range: MagicMock,
    app_context: None,
) -> None:
    """An authorised user receives the chart's form_data."""
    import superset.views.api as api_module

    mock_request = MagicMock()
    mock_request.args.get.return_value = "42"

    mock_slice = MagicMock()
    mock_slice.form_data = {"viz_type": "table", "metrics": ["count"]}
    query_chain = mock_db.session.query.return_value
    query_chain.filter_by.return_value.one_or_none.return_value = mock_slice
    mock_security_manager.raise_for_access.return_value = None

    view = _view_self()
    raw_fn = _get_view_func("query_form_data")

    with patch.object(api_module, "request", mock_request):
        raw_fn(view)

    mock_security_manager.raise_for_access.assert_called_once_with(chart=mock_slice)
    view.json_response.assert_called_once()
    call_args = view.json_response.call_args
    assert call_args[0][0] == {"viz_type": "table", "metrics": ["count"]}


@patch("superset.views.api.update_time_range")
@patch("superset.views.api.security_manager", new_callable=MagicMock)
@patch("superset.views.api.db")
def test_query_form_data_no_slice_returns_empty(
    mock_db: MagicMock,
    mock_security_manager: MagicMock,
    mock_update_time_range: MagicMock,
    app_context: None,
) -> None:
    """When no slice is found, an empty dict is returned without an access check."""
    import superset.views.api as api_module

    mock_request = MagicMock()
    mock_request.args.get.return_value = "999"
    query_chain = mock_db.session.query.return_value
    query_chain.filter_by.return_value.one_or_none.return_value = None

    view = _view_self()
    raw_fn = _get_view_func("query_form_data")

    with patch.object(api_module, "request", mock_request):
        raw_fn(view)

    mock_security_manager.raise_for_access.assert_not_called()
    view.json_response.assert_called_once()
    call_args = view.json_response.call_args
    assert call_args[0][0] == {}
