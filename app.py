import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import (
    Flask, jsonify, request, render_template, flash, redirect, url_for, session, Response,
    Blueprint, send_from_directory,
)
import razorpay
from types import SimpleNamespace
from uuid import uuid4

# Vercel/serverless deployments must use the Supabase data layer.
# The legacy backend uses a writable local SQLite file and cannot be used by
# Vercel functions. Keep the PostgreSQL backend available for local deployments
# that explicitly opt into it.
_USE_LEGACY_POSTGRES = (
    not os.environ.get("VERCEL")
    and (
        os.environ.get("USE_POSTGRES")
        or os.environ.get("USE_POSTGRESQL")
        or (os.environ.get("DATABASE_URL") and not os.environ.get("SUPABASE_URL"))
    )
)
if _USE_LEGACY_POSTGRES:
    from backend import *
else:
    from supabase_backend import *

from flask_mail import Mail, Message
from flask_socketio import SocketIO, emit
from functools import wraps
from datetime import timedelta, datetime, date
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
import csv