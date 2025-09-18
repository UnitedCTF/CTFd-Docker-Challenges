from CTFd.models import db


class DeploymentInstance(db.Model):
    """
    Ansible Container Tracker. This model stores the users/teams active ansible containers.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_or_team_id = db.Column("user_or_team_id", db.Integer, nullable=False, index=True)
    challenge_id = db.Column("challenge_id", db.Integer, nullable=False, index=True)
    in_progress = db.Column("in_progress", db.Boolean, nullable=False, default=True)
    deploy_id = db.Column("deploy_id", db.Integer)
    connection_info = db.Column("connection_info", db.Text)
    created_at = db.Column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )

    __table_args__ = (
        db.UniqueConstraint("user_or_team_id", "challenge_id", name="unique_team_user_challenge"),
    )
