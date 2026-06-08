"""0008 backfill can_manage_remediation capability

Capabilities are stored per-user (seeded from role at registration), so users
created before the remediation feature lack `can_manage_remediation` and would hit
403s on the new task endpoints. Grant it to the roles whose defaults now include
it (Admin, ComplianceOfficer); ReadOnly is intentionally excluded.

Revision ID: c3d9a1f70b22
Revises: b7e4c1a9f2d0
Create Date: 2026-06-08 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3d9a1f70b22'
down_revision: Union[str, None] = 'b7e4c1a9f2d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET capabilities = capabilities || '["can_manage_remediation"]'::jsonb
        WHERE role IN ('Admin', 'ComplianceOfficer')
          AND NOT (capabilities ? 'can_manage_remediation');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET capabilities = capabilities - 'can_manage_remediation'
        WHERE capabilities ? 'can_manage_remediation';
        """
    )
