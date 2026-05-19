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

from datetime import datetime
from typing import Optional
from unittest.mock import Mock, patch

import pytest

from superset.db_engine_specs.impala import ImpalaEngineSpec as spec  # noqa: N813
from superset.models.core import Database
from superset.models.sql_lab import Query
from superset.utils.network import is_safe_hostname
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CAST('2019-01-02' AS DATE)"),
        ("TimeStamp", "CAST('2019-01-02T03:04:05.678900' AS TIMESTAMP)"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_get_cancel_query_id() -> None:
    query = Query()

    cursor_mock = Mock()
    last_operation_mock = Mock()
    cursor_mock._last_operation = last_operation_mock

    guid = bytes(reversed(bytes.fromhex("9fbdba20000000006940643a2731718b")))
    last_operation_mock.handle.operationId.guid = guid

    assert (
        spec.get_cancel_query_id(cursor_mock, query)
        == "6940643a2731718b:9fbdba2000000000"
    )


@patch(
    "superset.db_engine_specs.impala.is_safe_hostname",
    return_value=True,
)
@patch("requests.post")
def test_cancel_query(post_mock: Mock, safe_host_mock: Mock) -> None:
    query = Query()
    database = Database(
        database_name="test_impala",
        sqlalchemy_uri="impala://impala.example.com:21050/default",
    )
    query.database = database

    response_mock = Mock()
    response_mock.status_code = 200
    post_mock.return_value = response_mock

    result = spec.cancel_query(None, query, "6940643a2731718b:9fbdba2000000000")

    safe_host_mock.assert_called_once_with("impala.example.com")
    post_mock.assert_called_once_with(
        "http://impala.example.com:25000/cancel_query?query_id=6940643a2731718b:9fbdba2000000000",
        timeout=3,
    )
    assert result is True


@patch(
    "superset.db_engine_specs.impala.is_safe_hostname",
    return_value=True,
)
@patch("requests.post")
def test_cancel_query_failed(post_mock: Mock, safe_host_mock: Mock) -> None:
    query = Query()
    database = Database(
        database_name="test_impala",
        sqlalchemy_uri="impala://impala.example.com:21050/default",
    )
    query.database = database

    response_mock = Mock()
    response_mock.status_code = 500
    post_mock.return_value = response_mock

    result = spec.cancel_query(None, query, "6940643a2731718b:9fbdba2000000000")

    post_mock.assert_called_once_with(
        "http://impala.example.com:25000/cancel_query?query_id=6940643a2731718b:9fbdba2000000000",
        timeout=3,
    )
    assert result is False


@patch(
    "superset.db_engine_specs.impala.is_safe_hostname",
    return_value=True,
)
@patch("requests.post")
def test_cancel_query_exception(post_mock: Mock, safe_host_mock: Mock) -> None:
    query = Query()
    database = Database(
        database_name="test_impala",
        sqlalchemy_uri="impala://impala.example.com:21050/default",
    )
    query.database = database

    post_mock.side_effect = Exception("Network error")

    result = spec.cancel_query(None, query, "6940643a2731718b:9fbdba2000000000")

    assert result is False


@pytest.mark.parametrize(
    "uri,expected_blocked",
    [
        ("impala://127.0.0.1:21050/default", True),
        ("impala://10.0.0.1:21050/default", True),
        ("impala://172.16.0.1:21050/default", True),
        ("impala://192.168.1.1:21050/default", True),
        ("impala://169.254.169.254:21050/default", True),
    ],
)
@patch("requests.post")
def test_cancel_query_ssrf_blocked(
    post_mock: Mock, uri: str, expected_blocked: bool
) -> None:
    """Verify cancel_query rejects hostnames resolving to private IPs."""
    query = Query()
    database = Database(database_name="test_impala", sqlalchemy_uri=uri)
    query.database = database

    result = spec.cancel_query(None, query, "6940643a2731718b:9fbdba2000000000")

    assert result is False
    post_mock.assert_not_called()


@patch("superset.utils.network.socket.getaddrinfo")
def test_is_safe_hostname_rejects_private_ip(mock_getaddrinfo: Mock) -> None:
    mock_getaddrinfo.return_value = [
        (None, None, None, None, ("10.0.0.1", 0)),
    ]
    assert is_safe_hostname("evil.example.com") is False


@patch("superset.utils.network.socket.getaddrinfo")
def test_is_safe_hostname_rejects_loopback(mock_getaddrinfo: Mock) -> None:
    mock_getaddrinfo.return_value = [
        (None, None, None, None, ("127.0.0.1", 0)),
    ]
    assert is_safe_hostname("localhost") is False


@patch("superset.utils.network.socket.getaddrinfo")
def test_is_safe_hostname_rejects_link_local(mock_getaddrinfo: Mock) -> None:
    mock_getaddrinfo.return_value = [
        (None, None, None, None, ("169.254.169.254", 0)),
    ]
    assert is_safe_hostname("metadata.internal") is False


@patch("superset.utils.network.socket.getaddrinfo")
def test_is_safe_hostname_allows_public_ip(mock_getaddrinfo: Mock) -> None:
    mock_getaddrinfo.return_value = [
        (None, None, None, None, ("8.8.8.8", 0)),
    ]
    assert is_safe_hostname("impala.example.com") is True


@patch("superset.utils.network.socket.getaddrinfo")
def test_is_safe_hostname_rejects_ipv6_loopback(mock_getaddrinfo: Mock) -> None:
    mock_getaddrinfo.return_value = [
        (None, None, None, None, ("::1", 0, 0, 0)),
    ]
    assert is_safe_hostname("ipv6-loopback.example.com") is False


@patch("superset.utils.network.socket.getaddrinfo")
def test_is_safe_hostname_rejects_ipv6_private(mock_getaddrinfo: Mock) -> None:
    mock_getaddrinfo.return_value = [
        (None, None, None, None, ("fd00::1", 0, 0, 0)),
    ]
    assert is_safe_hostname("ipv6-private.example.com") is False
