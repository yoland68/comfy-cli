import functools
import os
import uuid
import logging as logginglib
from mixpanel import Mixpanel, MixpanelException

import typer
from comfy_cli import logging, ui, constants
from comfy_cli.config_manager import ConfigManager

# Ignore logs from urllib3 that Mixpanel uses.
logginglib.getLogger("urllib3").setLevel(logginglib.ERROR)

MIXPANEL_TOKEN = "93aeab8962b622d431ac19800ccc9f67"
DISABLE_TELEMETRY = os.getenv("DISABLE_TELEMETRY", False)
mp = Mixpanel(MIXPANEL_TOKEN) if MIXPANEL_TOKEN else None

# Generate a unique tracing ID per command.
config_manager = ConfigManager()
cli_version = config_manager.get_cli_version()
tracing_id = str(uuid.uuid4())

app = typer.Typer()


@app.command()
def enable():
    set_tracking_enabled(True)
    typer.echo(f"Tracking is now {'enabled' if enable else 'disabled'}.")


@app.command()
def disable():
    set_tracking_enabled(False)
    typer.echo(f"Tracking is now {'enabled' if enable else 'disabled'}.")


def track_event(event_name: str, properties: any = None):
    logging.debug(f"tracking event called with event_name: {event_name} and properties: {properties}")
    enable_tracking = config_manager.get(constants.CONFIG_KEY_ENABLE_TRACKING)
    if not enable_tracking:
        return

    try:
        properties["cli_version"] = cli_version
        mp.track(distinct_id=tracing_id, event_name=event_name, properties=properties)
    except Exception as e:
        logging.warning(f"Failed to track event: {e}")  # Log the error but do not raise


def track_command(sub_command: str = None):
    """
    A decorator factory that logs the command function name and selected arguments when it's called.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            command_name = (
                f"{sub_command}:{func.__name__}"
                if sub_command is not None
                else func.__name__
            )

            # Copy kwargs to avoid mutating original dictionary
            # Remove context and ctx from the dictionary as they are not needed for tracking and not serializable.
            filtered_kwargs = {
                k: v for k, v in kwargs.items() if k != "ctx" and k != "context"
            }

            logging.debug(
                f"Tracking command: {command_name} with arguments: {filtered_kwargs}"
            )
            track_event(command_name, properties=filtered_kwargs)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def prompt_tracking_consent():
    tracking_enabled = config_manager.get(constants.CONFIG_KEY_ENABLE_TRACKING)
    if tracking_enabled is not None:
        return

    enable_tracking = ui.prompt_confirm_action(
        "Do you agree to enable tracking to improve the application?"
    )
    config_manager.set(constants.CONFIG_KEY_ENABLE_TRACKING, str(enable_tracking))

    # Note: only called once when the user interacts with the CLI for the
    #  first time iff the permission is granted.
    track_event("install")


def set_tracking_enabled(enabled: bool):
    config_manager.set(constants.CONFIG_KEY_ENABLE_TRACKING, str(enabled))
    return enabled
