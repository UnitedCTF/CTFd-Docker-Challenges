from flask import Blueprint, render_template

from CTFd.plugins.ansible_challenges.models.deployment_instance import (
    DeploymentInstance,
)
from CTFd.utils.config import is_teams_mode
from CTFd.utils.decorators import admins_only
from CTFd.models import Teams, Users, db


def define_ansible_status(app):
    admin_ansible_status = Blueprint(
        "admin_ansible_status",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )

    @admin_ansible_status.route("/admin/ansible_status", methods=["GET", "POST"])
    @admins_only
    def ansible_admin():
        with db.session.no_autoflush:  # We do this to prevent the session from being flushed when we modify the ansible tracker
            instances = DeploymentInstance.query.all()

            for instance in instances:
                if is_teams_mode():
                    team = Teams.query.filter_by(id=instance.team_id).first()
                    instance.team_id = team.name
                else:
                    user = Users.query.filter_by(id=instance.user_id).first()
                    instance.user_id = user.name

        return render_template("ansible_status.html", instances=instances)

    app.register_blueprint(admin_ansible_status)
