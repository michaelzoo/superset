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
import importlib
from unittest.mock import MagicMock, patch

import pytest

from superset.constants import CHANGE_ME_GAQ_JWT_SECRET
from superset.initialization import SupersetAppInitializer


def _make_initializer() -> SupersetAppInitializer:
    app = MagicMock()
    app.debug = False
    app.config = {
        "TESTING": False,
        "GLOBAL_ASYNC_QUERIES_JWT_SECRET": CHANGE_ME_GAQ_JWT_SECRET,
    }
    initializer = SupersetAppInitializer.__new__(SupersetAppInitializer)
    initializer.superset_app = app
    initializer.config = app.config
    return initializer


@patch("superset.initialization.async_query_manager_factory")
@patch("superset.initialization.feature_flag_manager")
def test_default_jwt_secret_rejected_in_production(
    mock_ff: MagicMock,
    mock_aqm: MagicMock,
) -> None:
    """Startup must abort when the default JWT secret is used in production."""
    initializer = _make_initializer()
    mock_ff.is_feature_enabled.return_value = True
    with pytest.raises(SystemExit):
        initializer.configure_async_queries()
    mock_aqm.init_app.assert_not_called()


@patch("superset.initialization.async_query_manager_factory")
@patch("superset.initialization.feature_flag_manager")
def test_default_jwt_secret_allowed_in_debug_mode(
    mock_ff: MagicMock,
    mock_aqm: MagicMock,
) -> None:
    """Debug mode should warn but not abort."""
    initializer = _make_initializer()
    mock_ff.is_feature_enabled.return_value = True
    initializer.superset_app.debug = True
    initializer.configure_async_queries()
    mock_aqm.init_app.assert_called_once()


@patch("superset.initialization.async_query_manager_factory")
@patch("superset.initialization.feature_flag_manager")
def test_default_jwt_secret_allowed_in_testing(
    mock_ff: MagicMock,
    mock_aqm: MagicMock,
) -> None:
    """TESTING mode should warn but not abort."""
    initializer = _make_initializer()
    mock_ff.is_feature_enabled.return_value = True
    initializer.superset_app.config["TESTING"] = True
    initializer.config["TESTING"] = True
    initializer.configure_async_queries()
    mock_aqm.init_app.assert_called_once()


@patch("superset.initialization.async_query_manager_factory")
@patch("superset.initialization.feature_flag_manager")
def test_custom_jwt_secret_accepted(
    mock_ff: MagicMock,
    mock_aqm: MagicMock,
) -> None:
    """A non-default secret should be accepted without issue."""
    initializer = _make_initializer()
    mock_ff.is_feature_enabled.return_value = True
    custom_secret = "a-very-secure-random-secret-that-is-long-enough"  # noqa: S105
    initializer.config["GLOBAL_ASYNC_QUERIES_JWT_SECRET"] = custom_secret
    initializer.superset_app.config["GLOBAL_ASYNC_QUERIES_JWT_SECRET"] = custom_secret
    initializer.configure_async_queries()
    mock_aqm.init_app.assert_called_once()


@patch("superset.initialization.async_query_manager_factory")
@patch("superset.initialization.feature_flag_manager")
def test_feature_disabled_skips_validation(
    mock_ff: MagicMock,
    mock_aqm: MagicMock,
) -> None:
    """When GLOBAL_ASYNC_QUERIES is disabled, no validation occurs."""
    initializer = _make_initializer()
    mock_ff.is_feature_enabled.return_value = False
    initializer.configure_async_queries()
    mock_aqm.init_app.assert_not_called()


def test_config_defaults_to_env_var() -> None:
    """GLOBAL_ASYNC_QUERIES_JWT_SECRET should read from the environment."""
    import superset.config as cfg

    env_secret = "env-provided-secret-value-for-jwt"  # noqa: S105
    with patch.dict("os.environ", {"GLOBAL_ASYNC_QUERIES_JWT_SECRET": env_secret}):
        importlib.reload(cfg)
        assert cfg.GLOBAL_ASYNC_QUERIES_JWT_SECRET == env_secret

    # Restore default after clearing env
    importlib.reload(cfg)
