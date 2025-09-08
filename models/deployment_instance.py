from CTFd.models import db

class DeploymentInstance(db.Model):
    """
    Ansible Container Tracker. This model stores the users/teams active ansible containers.
    """

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column("team_id", db.Integer, index=True)
    user_id = db.Column("user_id", db.Integer, index=True)
    challenge_id = db.Column("challenge_id", db.Integer, index=True)
    deploy_id = db.Column("deploy_id", db.Integer, index=True)
    connection_info = db.Column("connection_info", db.Text)
