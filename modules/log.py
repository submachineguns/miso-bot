import logging
from time import time


def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    # logger not created yet, assign options
    logger.setLevel(level=logging.INFO)
    fmt = logging.Formatter(
        fmt="{asctime} | {levelname:7} {name:>17} > {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    return logger


def get_command_logger():
    logger = logging.getLogger("command")
    if logger.handlers:
        return logger

    # logger not created yet, assign options
    logger.setLevel(level=logging.INFO)
    fmt = logging.Formatter(
        fmt="{asctime} | {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    return logger


def log_command(ctx, extra=""):
    try:
        took = time() - ctx.timer
    except AttributeError:
        took = 0
    command = str(ctx.command)
    guild = ctx.guild.name if ctx.guild is not None else "DM"
    user = str(ctx.author)
    return f'CMD {took:.2f}s {command:>15} > {guild} : {user} "{ctx.message.content}" {extra}'


def custom_command_format(ctx, keyword):
    guild = ctx.guild.name if ctx.guild is not None else "DM"
    user = str(ctx.author)
    return f'CMD_CUSTOM {keyword:>14} > {guild} : {user} "{ctx.message.content}"'
