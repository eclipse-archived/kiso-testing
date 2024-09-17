import getpass

import click

from .xray import extract_test_results, upload_test_results


@click.group()
@click.option(
    "-u",
    "--user",
    help="Xray user id",
    required=True,
    default=None,
    hide_input=True,
)
@click.option(
    "-p",
    "--password",
    help="Valid Xray API key (if not given ask at command prompt level)",
    required=False,
    default=None,
    hide_input=True,
)
@click.option(
    "--url",
    help="Base URL of Xray server",
    required=True,
)
@click.pass_context
def cli_xray(ctx: dict, user: str, password: str, url: str) -> None:
    """Xray interaction tool."""
    ctx.ensure_object(dict)
    ctx.obj["USER"] = user or input("Enter Client ID Xray and Press enter:")
    ctx.obj["PASSWORD"] = password or getpass.getpass("Enter your password and Press ENTER:")
    ctx.obj["URL"] = url


@cli_xray.command("upload")
@click.option(
    "--test-execution-id",
    help="Import the JUnit xml test results into an existing Test Execution ticket by overwriting",
    required=False,
    default=None,
    type=click.STRING,
)
@click.option(
    "-r",
    "--path-results",
    help="Full path to a JUnit report or to the folder containing the JUNIT reports",
    type=click.Path(exists=True, resolve_path=True),
    required=True,
)
@click.pass_context
def cli_upload(
    ctx,
    path_results: str,
    test_execution_id: str,
) -> None:
    """Upload the JUnit xml test results on xray."""
    # From the JUnit xml files found, create a temporary file to keep only the test results marked with an xray decorator.
    test_results = extract_test_results(path_results=path_results)

    # Upload the test results into Xray
    responses = upload_test_results(
        base_url=ctx.obj["URL"],
        user=ctx.obj["USER"],
        password=ctx.obj["PASSWORD"],
        results=test_results,
        test_execution_id=test_execution_id,
    )
    print(f"The test results can be found in JIRA by: {responses}")
