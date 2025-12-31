from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from application.models import Application
import subprocess
import os
import datetime
from ccu_project.settings import DATABASES
from django.core.cache import cache
from ccu_project.constants import QT_ST_CM_C, QT_ST_RJ_C, QT_ST_RJ_T, QT_ST_CM_T, QT_ST_GRPH
from quotagroup.views import plot_quota_time_new


@shared_task
def release_expired_locks():
    """
    Celery task to release expired application locks.

    Scans for applications that have been locked by operators for more than
    12 hours and releases those locks to prevent indefinite blocking of
    applications in case operators forget to unlock them.

    Returns:
        str: Status message with count of released locks.
    """
    expiration_time = timezone.now() - timedelta(hours=12)

    expired = Application.objects.filter(
        locked_by__isnull=False,
        locked_at__lt=expiration_time
    )

    count = expired.update(locked_by=None, locked_at=None)
    return f"Released {count} expired locks"


class PostgresBackup:
    """
    Utility class for managing PostgreSQL database backups.

    Provides methods for creating daily, weekly, and monthly backups of the
    application database using pg_dump with custom format compression.
    Handles backup rotation for weekly backups.

    Attributes:
        db_name (str): PostgreSQL database name from environment.
        db_user (str): PostgreSQL username from environment.
        db_password (str): PostgreSQL password from environment.
        db_host (str): PostgreSQL host from environment.
        db_port (int): PostgreSQL port from environment.
        backup_dir (str): Base directory for storing backup files.
    """

    db_name = os.getenv("DB_NAME", "none")
    db_user = os.getenv("DB_USER", "none")
    db_password = os.getenv("DB_PASSWORD", "none")
    db_host = os.getenv("DB_HOST", "none")
    db_port = int(os.getenv("DB_PORT", 5432))
    backup_dir = "/var/backups/postgres"

    @classmethod
    def _run_pg_dump(cls, output_path: str):
        """
        Execute pg_dump command to create database backup.

        Args:
            output_path (str): Full path where backup file should be saved.

        Raises:
            subprocess.CalledProcessError: If pg_dump command fails.
        """
        cmd = [
            "pg_dump",
            "-h", cls.db_host,
            "-p", str(cls.db_port),
            "-U", cls.db_user,
            "-F", "c",
            "-f", output_path,
            cls.db_name,
        ]
        env = os.environ.copy()
        env["PGPASSWORD"] = cls.db_password
        subprocess.run(cmd, env=env, check=True)

    @classmethod
    def backup_daily(cls):
        """
        Create daily database backup with date-based naming.

        Removes any existing backup for the current day before creating new one.

        Returns:
            str: Status message with backup file path.
        """
        path = os.path.join(cls.backup_dir, "daily")
        os.makedirs(path, exist_ok=True)

        today = datetime.date.today().isoformat()
        output = os.path.join(path, f"daily_{today}.dump")

        if os.path.exists(output):
            os.remove(output)

        cls._run_pg_dump(output)
        return f"Daily backup saved to {output}"

    @classmethod
    def backup_weekly(cls, keep_last=6):
        """
        Create weekly database backup with rotation of old backups.

        Maintains only the specified number of most recent weekly backups,
        removing older ones to conserve disk space.

        Args:
            keep_last (int): Number of most recent weekly backups to keep.

        Returns:
            str: Status message with backup file path.
        """
        path = os.path.join(cls.backup_dir, "weekly")
        os.makedirs(path, exist_ok=True)

        today = datetime.date.today().isoformat()
        output = os.path.join(path, f"weekly_{today}.dump")
        cls._run_pg_dump(output)

        files = sorted(
            [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".dump")]
        )
        if len(files) > keep_last:
            for f in files[:-keep_last]:
                os.remove(f)

        return f"Weekly backup saved to {output}"

    @classmethod
    def backup_monthly(cls):
        """
        Create monthly database backup with year-month naming.

        Removes any existing backup for the current month before creating new one.

        Returns:
            str: Status message with backup file path.
        """
        path = os.path.join(cls.backup_dir, "monthly")
        os.makedirs(path, exist_ok=True)

        today = datetime.date.today()
        output = os.path.join(path, f"monthly_{today.strftime('%Y-%m')}.dump")

        if os.path.exists(output):
            os.remove(output)

        cls._run_pg_dump(output)
        return f"Monthly backup saved to {output}"


@shared_task
def backup_postgres_daily():
    """
    Celery task to execute daily PostgreSQL backup.

    Returns:
        str: Status message from PostgresBackup.backup_daily().
    """
    return PostgresBackup.backup_daily()


@shared_task
def backup_postgres_weekly():
    """
    Celery task to execute weekly PostgreSQL backup with rotation.

    Returns:
        str: Status message from PostgresBackup.backup_weekly().
    """
    return PostgresBackup.backup_weekly()


@shared_task
def backup_postgres_monthly():
    """
    Celery task to execute monthly PostgreSQL backup.

    Returns:
        str: Status message from PostgresBackup.backup_monthly().
    """
    return PostgresBackup.backup_monthly()


@shared_task
def update_daily_statistics_graph():
    """
    Celery task to update the daily quota usage statistics graph.

    Calls plot_quota_time_new() to generate updated visualization and
    store it in cache for frontend display.

    Returns:
        None: Result from plot_quota_time_new() function.
    """
    plot_quota_time_new()