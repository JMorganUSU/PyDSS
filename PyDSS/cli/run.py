"""
CLI to run a PyDSS project
"""

import ast
import logging
import os
import sys
from pathlib import Path

import click

from PyDSS.pydss_project import PyDssProject
from PyDSS.loggers import setup_logging
from PyDSS.utils.utils import get_cli_string, make_human_readable_size
from PyDSS.common import SIMULATION_SETTINGS_FILENAME


logger = logging.getLogger(__name__)


@click.argument("project-path", type=click.Path(exists=True))
@click.option(
    "-o", "--options",
    help="dict-formatted simulation settings that override the config file. " \
            "Example:  pydss run ./project --options \"{\\\"Exports\\\": {\\\"Export Compression\\\": \\\"true\\\"}}\"",
)

@click.option(
    "-s", "--simulations-file",
    required=False,
    default = SIMULATION_SETTINGS_FILENAME,
    show_default=True,
    help="scenario toml file to run (over rides default)",
)

@click.option(
    "-t", "--tar-project",
    is_flag=True,
    default=False,
    show_default=True,
    help="Tar project files after successful execution."
)
@click.option(
    "-z", "--zip-project",
    is_flag=True,
    default=False,
    show_default=True,
    help="Zip project files after successful execution."
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    show_default=True,
    help="Enable verbose log output."
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    show_default=True,
    help="Dry run for getting estimated space."
)
@click.command()

def run(project_path, options=None, tar_project=False, zip_project=False, verbose=False, simulations_file=None, dry_run=False):
    """Run a PyDSS simulation."""
    project_path = Path(project_path)
    settings = PyDssProject.load_simulation_settings(project_path, simulations_file)
    if verbose:
        # Override the config file.
        settings.logging.logging_level = logging.DEBUG

    filename = None
    console_level = logging.INFO
    file_level = logging.INFO
    if not settings.logging.enable_console:
        console_level = logging.ERROR
    if verbose:
        console_level = logging.DEBUG
        file_level = logging.DEBUG
    if settings.logging.enable_file:
        logs_path = project_path / "Logs"
        if not logs_path.exists():
            logger.error("Logs path %s does not exist", logs_path)
            sys.exit(1)
        filename = logs_path / "pydss.log"

    setup_logging(
        "PyDSS",
        filename=filename,
        console_level=console_level,
        file_level=file_level,
    )
    logger.info("CLI: [%s]", get_cli_string())

    if options is not None:
        options = ast.literal_eval(options)
        if not isinstance(options, dict):
            logger.error("options are invalid: %s", options)
            sys.exit(1)

    project = PyDssProject.load_project(project_path, options=options, simulation_file=simulations_file)
    project.run(tar_project=tar_project, zip_project=zip_project, dry_run=dry_run)

    if dry_run:
        maxlen = max([len(k) for k in project.estimated_space.keys()])
        if len("ScenarioName") > maxlen:
            maxlen = len("ScenarioName")
        template = "{:<{width}}   {}\n".format("ScenarioName", "EstimatedSpace", width=maxlen)
        
        total_size = 0
        for k, v in project.estimated_space.items():
            total_size += v
            vstr = make_human_readable_size(v)
            template += "{:<{width}} : {}\n".format(k, vstr, width=maxlen)
        template = template.strip()
        logger.info(template)
        logger.info("-"*30)
        logger.info(f"TotalSpace: {make_human_readable_size(total_size)}")
        logger.info("="*30)
        logger.info("Note: compression may reduce the size by ~90% depending on the data.")

