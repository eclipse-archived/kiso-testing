##########################################################################
# Copyright (c) 2010-2022 Robert Bosch GmbH
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# http://www.eclipse.org/legal/epl-2.0.
#
# SPDX-License-Identifier: EPL-2.0
##########################################################################

import copy
import logging
import pathlib
import signal
from contextlib import nullcontext as does_not_raise
from pathlib import Path
from typing import Any
from unittest import TestCase, TestResult

import pytest
from pytest_mock import MockerFixture

import pykiso
import pykiso.test_coordinator.test_execution
from pykiso import CChannel, DTAuxiliaryInterface
from pykiso.config_parser import parse_config
from pykiso.lib.auxiliaries.mp_proxy_auxiliary import MpProxyAuxiliary
from pykiso.lib.auxiliaries.proxy_auxiliary import ProxyAuxiliary
from pykiso.lib.connectors.cc_mp_proxy import CCMpProxy
from pykiso.lib.connectors.cc_proxy import CCProxy
from pykiso.test_coordinator import test_execution
from pykiso.test_setup.config_registry import (
    ConfigRegistry,
    DynamicImportLinker,
)


@pytest.mark.parametrize("tmp_test", [("aux1", "aux2", False)], indirect=True)
def test_test_execution(tmp_test, capsys):
    """Call execute function from test_execution using
    configuration data coming from parse_config method

    Validation criteria:
        -  run is executed without error
    """
    cfg = parse_config(tmp_test)
    ConfigRegistry.register_aux_con(cfg)
    exit_code = test_execution.execute(cfg, pattern_inject="*.py::MyTest*")
    ConfigRegistry.delete_aux_con()

    output = capsys.readouterr()
    assert "FAIL" not in output.err
    assert "RUNNING TEST: " in output.err
    assert "END OF TEST: " in output.err
    assert "->  PASSED" in output.err
    assert "->  FAILED" not in output.err
    assert exit_code == test_execution.ExitCode.ALL_TESTS_SUCCEEDED


@pytest.mark.parametrize("tmp_test", [("aux3", "aux4", False)], indirect=True)
def test_config_registry(tmp_test):
    """Call execute function from test_execution using
    configuration data coming from parse_config method

    Validation criteria:
        -  run is executed without error
    """
    cfg = parse_config(tmp_test)

    with ConfigRegistry.provide_auxiliaries(cfg):

        assert isinstance(ConfigRegistry.get_aux_by_alias("aux3"), DTAuxiliaryInterface)

        auxes_by_type = ConfigRegistry.get_auxes_by_type(DTAuxiliaryInterface)
        assert isinstance(auxes_by_type, dict)

        all_auxes = ConfigRegistry.get_all_auxes()
        # all auxiliaries are subclasses of DTAuxiliaryInterface, thus the expected equality
        assert all_auxes == auxes_by_type

        aux3_config = ConfigRegistry.get_aux_config("aux3")
        assert tuple(aux3_config.keys()) == ("com",)
        assert isinstance(aux3_config["com"], CChannel)

        assert ConfigRegistry.get_auxes_alias() == ["aux3", "aux4"]


@pytest.mark.parametrize("tmp_test", [("aux1", "aux2", False)], indirect=True)
def test_test_execution_with_pattern(tmp_test, capsys):
    """Call execute function from test_execution using
    configuration data coming from parse_config method
    by specifying a pattern

    Validation criteria:
        -  run is executed without error
    """
    cfg = parse_config(tmp_test)
    ConfigRegistry.register_aux_con(cfg)
    exit_code = test_execution.execute(cfg, pattern_inject="my_test.py")
    ConfigRegistry.delete_aux_con()

    output = capsys.readouterr()
    assert "FAIL" not in output.err
    assert "Ran 0 tests" in output.err
    assert exit_code == test_execution.ExitCode.ALL_TESTS_SUCCEEDED


@pytest.mark.parametrize(
    "tmp_test", [("aux1_badtag", "aux2_badtag", False)], indirect=True
)
def test_test_execution_with_bad_user_tags(tmp_test, capsys):
    """Call execute function from test_execution using
    configuration data coming from parse_config method
    with an undefined user tag.

    Validation criteria:
        -  'SKIPPED' is present in test output
    """
    user_tags = {"unknown-variant": ["will raise"]}
    cfg = parse_config(tmp_test)
    ConfigRegistry.register_aux_con(cfg)
    exit_code = test_execution.execute(cfg, user_tags=user_tags)
    ConfigRegistry.delete_aux_con()

    assert exit_code == test_execution.ExitCode.BAD_CLI_USAGE


@pytest.mark.parametrize("tmp_test", [("aux1_tags", "aux2_tags", False)], indirect=True)
def test_test_execution_with_user_tags(tmp_test, capsys):
    """Call execute function from test_execution using
    configuration data coming from parse_config method
    with additional user tags.

    Validation criteria:
        -  'SKIPPED' is present in test output
    """
    user_tags = {"variant": ["to be skipped"]}
    cfg = parse_config(tmp_test)
    ConfigRegistry.register_aux_con(cfg)
    exit_code = test_execution.execute(cfg, user_tags=user_tags)
    ConfigRegistry.delete_aux_con()

    output = capsys.readouterr()
    assert "FAIL" not in output.err
    assert "SKIPPED TEST" in output.err
    assert exit_code == test_execution.ExitCode.ALL_TESTS_SUCCEEDED


def test_config_registry_context_manager(tmp_test, mocker):
    mock_register_aux_con = mocker.patch.object(ConfigRegistry, "register_aux_con")
    mocker_delete_aux_con = mocker.patch.object(ConfigRegistry, "delete_aux_con")

    cfg = parse_config(tmp_test)

    with ConfigRegistry.provide_auxiliaries(cfg):
        pass

    mock_register_aux_con.assert_called_once_with(cfg)
    mocker_delete_aux_con.assert_called_once_with()


def test_parse_test_selection_pattern():
    test_file_pattern = ()
    test_file_pattern = test_execution.parse_test_selection_pattern("first::")
    assert test_file_pattern.test_file == "first"
    assert test_file_pattern.test_class == None
    assert test_file_pattern.test_case == None

    test_file_pattern = test_execution.parse_test_selection_pattern(
        "first::second::third"
    )
    assert test_file_pattern.test_file == "first"
    assert test_file_pattern.test_class == "second"
    assert test_file_pattern.test_case == "third"

    test_file_pattern = test_execution.parse_test_selection_pattern("first::::third")
    assert test_file_pattern.test_file == "first"
    assert test_file_pattern.test_class == None
    assert test_file_pattern.test_case == "third"

    test_file_pattern = test_execution.parse_test_selection_pattern("::second::third")
    assert test_file_pattern.test_file == None
    assert test_file_pattern.test_class == "second"
    assert test_file_pattern.test_case == "third"


@pytest.mark.parametrize(
    "tmp_test", [("aux1_collect", "aux2_collect", False)], indirect=True
)
def test_test_execution_collect_error(tmp_test, capsys, mocker):
    """Call execute function from test_execution using
    configuration data coming from parse_config method
    by specifying a pattern

    Validation criteria:
        -  run is executed without error
    """
    mocker.patch(
        "pykiso.test_coordinator.test_suite.tc_sort_key", side_effect=Exception
    )

    cfg = parse_config(tmp_test)
    ConfigRegistry.register_aux_con(cfg)

    with pytest.raises(pykiso.TestCollectionError):
        test_execution.collect_test_suites(cfg["test_suite_list"])

    ConfigRegistry.delete_aux_con()

    output = capsys.readouterr()
    assert "FAIL" not in output.err
    assert "Ran 0 tests" not in output.err


@pytest.mark.parametrize(
    "paths, pattern, expected",
    [
        ([pathlib.Path("test_module.py")], "test_*", None),
        (
            [pathlib.Path("test_module.py"), pathlib.Path("test_module_1.py")],
            "test_module*",
            None,
        ),
    ],
)
def test__check_module_names(paths, pattern, expected, mocker):
    mock_glob = mocker.patch("pathlib.Path.glob", return_value=paths)
    test_dir = "test_dir"

    actual = test_execution._check_module_names(test_dir, pattern)
    assert actual == expected
    mock_glob.assert_called_with(pattern)


@pytest.mark.parametrize(
    "paths, pattern",
    [
        ([pathlib.Path("test_module-1.py")], "test_*"),
        (
            [pathlib.Path("test_module.py"), pathlib.Path("test_module-1.py")],
            "test_module*",
        ),
    ],
)
def test__check_module_names_invalid(paths, pattern, mocker):
    mock_glob = mocker.patch("pathlib.Path.glob", return_value=paths)
    test_dir = "test_dir"

    with pytest.raises(pykiso.InvalidTestModuleName) as exec_info:
        test_execution._check_module_names(test_dir, pattern)

    mock_glob.assert_called_with(pattern)

    assert (
        f"Test files need to be valid python module names but 'test_module-1.py' is invalid"
        in exec_info.value.message
    )


@pytest.mark.parametrize("tmp_test", [("aux1", "aux2", False)], indirect=True)
def test_collect_suites_with_invalid_cli_pattern(tmp_test, mocker):
    """Call collect_test_suites function from test_execution using
    configuration data coming from parse_config method and specifying a invalid
    pattern from cli

    Validation criteria:
        - run is executed with TestCollectionError
    """
    mock_check = mocker.patch(
        "pykiso.test_coordinator.test_execution._check_module_names",
        side_effect=pykiso.InvalidTestModuleName("test_module-1.py"),
    )
    pattern = "test_module*"

    cfg = parse_config(tmp_test)

    ConfigRegistry.register_aux_con(cfg)

    with pytest.raises(pykiso.TestCollectionError):
        test_execution.collect_test_suites(
            cfg["test_suite_list"],
            test_filter_pattern=pattern,
        )

    mock_check.assert_called_with(
        start_dir=cfg["test_suite_list"][0]["suite_dir"],
        pattern=pattern,
    )

    ConfigRegistry.delete_aux_con()


@pytest.mark.parametrize("tmp_test", [("aux1", "aux2", False)], indirect=True)
def test_collect_suites_with_invalid_cfg_pattern(tmp_test, mocker):
    """Call collect_test_suites function from test_execution using
    configuration data coming from parse_config method and specifying a invalid
    pattern in the cfg

    Validation criteria:
        - run is executed with TestCollectionError
    """
    mock_check = mocker.patch(
        "pykiso.test_coordinator.test_execution._check_module_names",
        side_effect=pykiso.InvalidTestModuleName("test_module-1.py"),
    )

    pattern = "test_module*"

    cfg = parse_config(tmp_test)
    cfg["test_suite_list"][0]["test_filter_pattern"] = pattern

    ConfigRegistry.register_aux_con(cfg)

    with pytest.raises(pykiso.TestCollectionError):
        test_execution.collect_test_suites(cfg["test_suite_list"])

    mock_check.assert_called_with(
        start_dir=cfg["test_suite_list"][0]["suite_dir"],
        pattern=pattern,
    )

    ConfigRegistry.delete_aux_con()


@pytest.mark.parametrize(
    "tmp_test",
    [("collector_error_2_aux1", "collector_error_2_aux", False)],
    indirect=True,
)
def test_test_execution_collect_error_log(mocker, caplog, tmp_test):
    """Call execute function from test_execution using
    configuration data coming from parse_config method
    by specifying a pattern

    Validation criteria:
        -  run is executed with test collection error
    """
    mocker.patch(
        "pykiso.test_coordinator.test_execution.collect_test_suites",
        side_effect=pykiso.TestCollectionError("test"),
    )

    cfg = parse_config(tmp_test)

    with caplog.at_level(logging.ERROR):
        exit_code = test_execution.execute(config=cfg)

    assert "Error occurred during test collection." in caplog.text
    assert (
        exit_code
        == test_execution.ExitCode.ONE_OR_MORE_TESTS_RAISED_UNEXPECTED_EXCEPTION
    )


@pytest.mark.parametrize(
    "tmp_test", [("creation_error_aux1", "creation_error_aux2", False)], indirect=True
)
def test_test_execution_with_auxiliary_creation_error(mocker, caplog, tmp_test):
    """Call execute function from test_execution using
    configuration data coming from parse_config method
    by specifying a pattern

    Validation criteria:
        -  run is executed with auxiliary creation error
    """
    mocker.patch(
        "pykiso.test_coordinator.test_execution.collect_test_suites",
        side_effect=pykiso.AuxiliaryCreationError("test"),
    )
    cfg = parse_config(tmp_test)

    with caplog.at_level(logging.ERROR):
        exit_code = test_execution.execute(config=cfg)

    assert "Error occurred during auxiliary creation." in caplog.text
    assert exit_code == test_execution.ExitCode.AUXILIARY_CREATION_FAILED


@pytest.mark.parametrize("tmp_test", [("text_aux1", "text_aux2", False)], indirect=True)
def test_test_execution_with_text_reporting(tmp_test, capsys):
    """Call execute function from test_execution using
    configuration data coming from parse_config method and
    --text option to show the test results only in console

    Validation criteria:
        -  run is executed without error
    """
    cfg = parse_config(tmp_test)
    report_option = "text"
    ConfigRegistry.register_aux_con(cfg)
    exit_code = test_execution.execute(cfg, report_option)
    ConfigRegistry.delete_aux_con()

    output = capsys.readouterr()
    assert "FAIL" not in output.err
    assert "RUNNING TEST: " in output.err
    assert "END OF TEST: " in output.err
    assert "->  PASSED" in output.err
    assert "->  FAILED" not in output.err


@pytest.mark.parametrize(
    "tmp_test",
    [("fail_aux1", "fail_aux2", True), ("err_aux1", "err_aux2", None)],
    ids=["test failed", "error occurred"],
    indirect=True,
)
def test_test_execution_test_failure(tmp_test, capsys):
    """Call execute function from test_execution using
    configuration data coming from parse_config method and
    --text option to show the test results only in console

    Validation criteria:
        -  run is executed with error
        -  error is shown in banner and in final result
    """
    cfg = parse_config(tmp_test)
    ConfigRegistry.register_aux_con(cfg)
    exit_code = test_execution.execute(cfg)
    ConfigRegistry.delete_aux_con()

    output = capsys.readouterr()
    assert "FAIL" in output.err
    assert "RUNNING TEST: " in output.err
    assert "END OF TEST: " in output.err
    assert "->  FAILED" in output.err


@pytest.mark.parametrize(
    "tmp_test", [("juint_aux1", "juint_aux2", False)], indirect=True
)
def test_test_execution_with_junit_reporting(tmp_test, capsys, mocker):
    """Call execute function from test_execution using
    configuration data coming from parse_config method and
    --junit option to show the test results in console
    and to generate a junit xml report

    Validation criteria:
        -  run is executed without error
    """

    class HasSubstring(str):
        """Test if string is in passed argument"""

        def __eq__(self, other: Any):
            return self in str(other)

    cfg = parse_config(tmp_test)
    report_option = "junit"
    mock_open = mocker.patch("builtins.open")
    test_name = "banana"
    ConfigRegistry.register_aux_con(cfg)
    test_execution.execute(cfg, report_option, report_name=test_name)
    ConfigRegistry.delete_aux_con()
    mock_open.assert_called_with(HasSubstring(test_name), "wb")

    output = capsys.readouterr()
    assert "FAIL" not in output.err
    assert "RUNNING TEST: " in output.err
    assert "END OF TEST: " in output.err
    assert "PASSED" in output.err


@pytest.mark.parametrize("tmp_test", [("step_aux1", "step_aux2", False)], indirect=True)
def test_test_execution_with_step_report(tmp_test, capsys):
    """Call execute function from test_execution using
    configuration data coming from parse_config method

    Validation criteria:
        -  creates step report file
    """
    cfg = parse_config(tmp_test)
    ConfigRegistry.register_aux_con(cfg)
    exit_code = test_execution.execute(cfg, step_report="step_report.html")
    ConfigRegistry.delete_aux_con()

    output = capsys.readouterr()
    assert "RUNNING TEST: " in output.err
    assert "END OF TEST: " in output.err
    assert "->  PASSED" in output.err
    assert pathlib.Path("step_report.html").is_file()


def test_failure_and_error_handling():
    TR_ALL_TESTS_SUCCEEDED = TestResult()
    TR_ONE_OR_MORE_TESTS_FAILED = TestResult()
    TR_ONE_OR_MORE_TESTS_FAILED.failures = [TestCase()]
    TR_ONE_OR_MORE_TESTS_RAISED_UNEXPECTED_EXCEPTION = TestResult()
    TR_ONE_OR_MORE_TESTS_RAISED_UNEXPECTED_EXCEPTION.errors = [TestCase()]
    TR_ONE_OR_MORE_TESTS_FAILED_AND_RAISED_UNEXPECTED_EXCEPTIONE = TestResult()
    TR_ONE_OR_MORE_TESTS_FAILED_AND_RAISED_UNEXPECTED_EXCEPTIONE.errors = [TestCase()]
    TR_ONE_OR_MORE_TESTS_FAILED_AND_RAISED_UNEXPECTED_EXCEPTIONE.failures = [TestCase()]

    assert test_execution.failure_and_error_handling(TR_ALL_TESTS_SUCCEEDED) == 0
    assert test_execution.failure_and_error_handling(TR_ONE_OR_MORE_TESTS_FAILED) == 1
    assert (
        test_execution.failure_and_error_handling(
            TR_ONE_OR_MORE_TESTS_RAISED_UNEXPECTED_EXCEPTION
        )
        == 2
    )
    assert (
        test_execution.failure_and_error_handling(
            TR_ONE_OR_MORE_TESTS_FAILED_AND_RAISED_UNEXPECTED_EXCEPTIONE
        )
        == 3
    )


@pytest.mark.parametrize(
    "tc_tags, cli_tags, expected_error, expect_skip",
    [
        pytest.param(
            {"-some_tag_": ["value"]},  # tc_tags
            {"_some-tag": ["other_value"]},  # cli_tags
            does_not_raise(),
            True,  # expect_skip
            id="insensitivity to dashes and underscores",
        ),
        pytest.param(
            None,  # tc_tags
            {},  # cli_tags
            does_not_raise(),
            False,
            id="no tags in tc nor in cli",
        ),
        pytest.param(
            None,  # tc_tags
            {"k1": "v1"},  # cli_tags
            pytest.raises(NameError),
            True,
            id="no tags in tc but in cli",
        ),
        pytest.param(
            {
                "k1": ["v1", "v3"],
                "k2": ["v2", "v5", "v6"],
            },  # tc_tags
            {"k1": "v2"},  # cli_tags
            does_not_raise(),
            True,  # expect_skip
            id="one tag name matches but no value",
        ),
        pytest.param(
            {
                "k1": ["v1", "v3"],
                "k2": ["v2", "v5", "v6"],
            },  # tc_tags
            {"k1": "v1", "k2": ["v12", "v13"]},  # cli_tags
            does_not_raise(),
            True,  # expect_skip
            id="multple tag names match but no value",
        ),
        pytest.param(
            {
                "k1": ["v1", "v3"],
                "k2": ["v2", "v5", "v6"],
            },  # tc_tags
            {
                "k1": "v1",
                "k2": "v2",
            },  # cli_tags
            does_not_raise(),
            False,  # expect_skip
            id="multiple tag names match and multiple values",
        ),
        pytest.param(
            {
                "k1": ["v1", "v7"],
                "k2": ["v2", "v5", "v6"],
            },  # tc_tags
            {"k3": "v10"},  # cli_tags
            pytest.raises(NameError),
            True,  # expect_skip
            id="no name matches, multiple tc tags",
        ),
        pytest.param(
            {"k1": ["v1", "v3"]},  # tc_tags
            {"k2": ["v2", "v5"]},  # cli_tags
            pytest.raises(NameError),
            True,  # expect_skip
            id="no name matches, single tc tags",
        ),
        pytest.param(
            {
                "k1": ["v1", "v3"],
                "k2": ["v2", "v5", "v6"],
            },  # tc_tags
            {"k1": "v1"},  # cli_tags
            does_not_raise(),
            False,  # expect_skip
            id="one name matches and one value",
        ),
        pytest.param(
            {
                "k1": ["v1", "v3"],
                "k2": ["v2", "v5", "v6"],
            },  # tc_tags
            {"k1": ["v1", "v3"]},  # cli_tags
            does_not_raise(),
            False,  # expect_skip
            id="one name matches and multiple values",
        ),
        pytest.param(
            {
                "k1": ["v1", "v3"],
                "k2": ["v2", "v5", "v6"],
            },  # tc_tags
            {"k1": ["v1", "v3"], "k2": ["v2", "v5"]},  # cli_tags
            does_not_raise(),
            False,  # expect_skip
            id="multiple names match and multiple values",
        ),
    ],
)
def test_apply_variant_filter(tc_tags, cli_tags, expect_skip, expected_error, mocker):
    mock_test_case = mocker.Mock()
    mock_test_case.tag = tc_tags
    mock_flatten = mocker.patch(
        "pykiso.test_coordinator.test_execution.test_suite.flatten",
        return_value=[mock_test_case],
    )

    with expected_error:
        test_execution.apply_tag_filter({}, cli_tags)

        # case where nothing was raised
        assert mock_flatten.call_count == 2
        if not expect_skip:
            assert not hasattr(mock_test_case, "__unittest_skip__")
            assert not hasattr(mock_test_case, "__unittest_skip_why__")
        else:
            assert mock_test_case.__unittest_skip__ == True
            assert mock_test_case.__unittest_skip_why__ == mock_test_case._skip_msg


def test_apply_variant_filter_multiple_testcases(mocker):
    cli_tags = {"k1": ["v1"]}

    mock_test_case_to_run = mocker.Mock()
    mock_test_case_to_run.tag = {"k1": ["v1"], "k2": ["v2"]}

    mock_test_case_to_skip = mocker.Mock()
    mock_test_case_to_skip.tag = {"k3": ["v1", "v3"]}
    mock_flatten = mocker.patch(
        "pykiso.test_coordinator.test_execution.test_suite.flatten",
        return_value=[mock_test_case_to_run, mock_test_case_to_skip],
    )

    test_execution.apply_tag_filter({}, cli_tags)

    assert mock_flatten.call_count == 2
    assert not hasattr(mock_test_case_to_run, "__unittest_skip__")
    assert not hasattr(mock_test_case_to_run, "__unittest_skip_why__")
    assert mock_test_case_to_skip.__unittest_skip__ == True
    assert (
        "'k1' not present in test tags" in mock_test_case_to_skip.__unittest_skip_why__
    )


def test_apply_test_case_filter(mocker):
    mock_test_case = mocker.Mock()
    mock_test_case.setUp = None
    mock_test_case.tearDown = None
    mock_test_case.testMethodName = None
    mock_test_case.skipTest = lambda x: x  # return input
    mock_test_case.tag = None
    mock_test_case._testMethodName = "testMethodName"
    mock_test_case.__class__.__name__ = "testClass1"

    test_cases = []
    for id in range(10):
        mock_test_case._testMethodName = f"test_run_{id}"
        test_cases.append(copy.deepcopy(mock_test_case))

    mock = mocker.patch(
        "pykiso.test_coordinator.test_execution.test_suite.flatten",
        return_value=test_cases,
    )

    new_testsuite = test_execution.apply_test_case_filter(
        {}, "testClass1", "test_run_[2-5]"
    )
    assert len(new_testsuite._tests) == 4
    assert new_testsuite._tests[0]._testMethodName == "test_run_2"
    assert new_testsuite._tests[1]._testMethodName == "test_run_3"
    assert new_testsuite._tests[2]._testMethodName == "test_run_4"
    assert new_testsuite._tests[3]._testMethodName == "test_run_5"

    new_testsuite = test_execution.apply_test_case_filter({}, "testClass1", None)
    assert len(new_testsuite._tests) == 10

    new_testsuite = test_execution.apply_test_case_filter(
        {}, "NotExistingTestClass", None
    )
    assert len(new_testsuite._tests) == 0


@pytest.fixture
def sample_config(mocker: MockerFixture, request: pytest.FixtureRequest):
    config = {
        "auxiliaries": {
            "aux1": {
                "connectors": {"com": "channel1"},
                "config": {"aux_param1": 1},
                "type": "some_module:Auxiliary",
            },
            "aux2": {
                "connectors": {"com": "channel1"},
                "config": {"aux_param2": 2},
                "type": "some_other_module:SomeOtherAuxiliary",
            },
        },
        "connectors": {
            "channel1": {
                "config": {"channel_param": 42},
                "type": "channel_module:SomeCChannel",
            }
        },
    }

    # set additional config parameters based on provided fixture params
    mp_enable, aux1_auto_start, aux2_auto_start = getattr(
        request, "param", (False, False, False)
    )

    if mp_enable:
        config["connectors"]["channel1"]["config"]["processing"] = True
        cc_class = CCMpProxy
        aux_class = MpProxyAuxiliary
    else:
        cc_class = CCProxy
        aux_class = ProxyAuxiliary

    if aux1_auto_start is not None:
        config["auxiliaries"]["aux1"]["config"]["auto_start"] = aux1_auto_start
    if aux2_auto_start is not None:
        config["auxiliaries"]["aux2"]["config"]["auto_start"] = aux2_auto_start

    expected_provide_connector_calls = [
        mocker.call(
            "channel1",
            "channel_module:SomeCChannel",
            **config["connectors"]["channel1"]["config"],
        ),
        mocker.call("proxy_channel_aux1", f"{cc_class.__module__}:{cc_class.__name__}"),
        mocker.call("proxy_channel_aux2", f"{cc_class.__module__}:{cc_class.__name__}"),
    ]

    # auto_start is expected to be set if any of the attached auxiliaries has it explicitely set
    # or if it isn't specified (default is auto_start enabled)
    expected_proxy_auto_start = aux1_auto_start in (True, None) or aux2_auto_start in (
        True,
        None,
    )

    # expected additional kwargs for the provide_auxiliary calls
    expected_aux1_params = {"aux_param1": 1}
    if aux1_auto_start is not None:
        expected_aux1_params.update({"auto_start": aux1_auto_start})
    expected_aux2_params = {"aux_param2": 2}
    if aux2_auto_start is not None:
        expected_aux2_params.update({"auto_start": aux2_auto_start})

    expected_provide_auxiliary_calls = [
        mocker.call(
            "aux1",
            "some_module:Auxiliary",
            aux_cons={"com": "proxy_channel_aux1"},
            **expected_aux1_params,
        ),
        mocker.call(
            "aux2",
            "some_other_module:SomeOtherAuxiliary",
            aux_cons={"com": "proxy_channel_aux2"},
            **expected_aux2_params,
        ),
        mocker.call(
            "proxy_aux_channel1",
            f"{aux_class.__module__}:{aux_class.__name__}",
            aux_cons={"com": "channel1"},
            aux_list=["aux1", "aux2"],
            auto_start=expected_proxy_auto_start,
        ),
    ]

    return config, expected_provide_connector_calls, expected_provide_auxiliary_calls


@pytest.mark.parametrize(
    "sample_config",
    # execute sample_config fixture with the parameters
    # multiprocessing_enabled, aux1_auto_start, aux2_auto_start
    [
        (True, True, True),
        (False, True, True),
        (False, False, True),
        (False, False, False),
        (False, None, False),
        (False, None, None),
    ],
    indirect=True,
    ids=[
        "multiprocessing - auto start",
        "threading - auto start",
        "threading - no auto start aux1",
        "threading - no auto start all auxes",
        "threading - default auto start aux1",
        "threading - default auto start all auxes",
    ],
)
def test_config_registry_auto_proxy(mocker: MockerFixture, sample_config):
    mock_linker = mocker.MagicMock()
    mocker.patch(
        "pykiso.test_setup.config_registry.DynamicImportLinker",
        return_value=mock_linker,
    )

    config, provide_connector_calls, provide_auxiliary_calls = sample_config

    ConfigRegistry.register_aux_con(config)

    mock_linker.install.assert_called_once()
    mock_linker.provide_connector.assert_has_calls(
        provide_connector_calls, any_order=True
    )
    mock_linker.provide_auxiliary.assert_has_calls(
        provide_auxiliary_calls, any_order=True
    )
    mock_linker._aux_cache.get_instance.assert_called_once_with("proxy_aux_channel1")


def test_config_registry_auto_proxy_creation_error(
    mocker: MockerFixture, sample_config
):
    mock_linker = mocker.MagicMock()
    mocker.patch(
        "pykiso.test_setup.config_registry.DynamicImportLinker",
        return_value=mock_linker,
    )
    mock_delete_aux_con = mocker.patch.object(ConfigRegistry, "delete_aux_con")
    mocker.patch.object(
        ConfigRegistry,
        "get_aux_by_alias",
        side_effect=pykiso.exceptions.AuxiliaryCreationError("proxy_aux_channel1"),
    )

    config, provide_connector_calls, provide_auxiliary_calls = sample_config

    with pytest.raises(pykiso.exceptions.AuxiliaryCreationError):
        ConfigRegistry.register_aux_con(config)

    mock_linker.install.assert_called_once()
    mock_linker.provide_connector.assert_has_calls(
        provide_connector_calls, any_order=True
    )
    mock_linker.provide_auxiliary.assert_has_calls(
        provide_auxiliary_calls, any_order=True
    )
    mock_delete_aux_con.assert_called_once()


def test_config_registry_no_auto_proxy(mocker: MockerFixture, sample_config):
    mock_make_px_channel = mocker.patch.object(
        ConfigRegistry, "_make_proxy_channel_config"
    )
    mock_make_px_aux = mocker.patch.object(ConfigRegistry, "_make_proxy_aux_config")
    mock_linker = mocker.MagicMock()
    mocker.patch(
        "pykiso.test_setup.config_registry.DynamicImportLinker",
        return_value=mock_linker,
    )

    config, *_ = sample_config
    config["auxiliaries"]["aux2"]["connectors"]["com"] = "other_channel"

    ConfigRegistry.register_aux_con(config)

    mock_make_px_channel.assert_not_called()
    mock_make_px_aux.assert_not_called()

    mock_linker.install.assert_called_once()
    assert mock_linker.provide_connector.call_count == 1
    assert mock_linker.provide_auxiliary.call_count == 2
    mock_linker._aux_cache.get_instance.assert_not_called()


def test_abort(mocker: MockerFixture, caplog):
    reason = "reason"
    os_kill_mock = mocker.patch("os.kill")

    test_execution.abort(reason)

    assert reason in caplog.text
    assert (
        "Non recoverable error occurred during test execution, aborting test session."
        in caplog.text
    )
    os_kill_mock.assert_called_once()
