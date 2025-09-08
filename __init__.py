import hashlib
import json
from datetime import datetime
from typing import Any, cast
from urllib.parse import urljoin

from pydantic import BaseModel
import requests
from flask import (
    Blueprint,
    abort,
    render_template,
    request,
)
from flask_restx import Namespace, Resource

from CTFd.api import CTFd_API_v1
from CTFd.api.v1.helpers.request import validate_args
from CTFd.models import (
    Teams,
    Users,
    db,
)
from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES
from CTFd.utils.config import is_teams_mode
from CTFd.utils.dates import unix_time
from CTFd.utils.decorators import (
    admins_only,
    authed_only,
)
from CTFd.utils.user import get_current_team, get_current_user, is_admin

from .admin_config import DockerConfig, define_docker_admin
from .challenge_type import DockerChallenge, DockerChallengeType


class DockerChallengeTracker(db.Model):
    """
    Docker Container Tracker. This model stores the users/teams active docker containers.
    """

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column("team_id", db.Integer, index=True)
    user_id = db.Column("user_id", db.Integer, index=True)
    challenge_id = db.Column("challenge_id", db.Integer, index=True)
    deploy_id = db.Column("deploy_id", db.Integer, index=True)
    connection_info = db.Column("connection_info", db.Text)


def define_docker_status(app):
    admin_docker_status = Blueprint(
        "admin_docker_status",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )

    @admin_docker_status.route("/admin/docker_status", methods=["GET", "POST"])
    @admins_only
    def docker_admin():
        # docker_config = DockerConfig.query.filter_by(id=1).first()
        with db.session.no_autoflush:  # We do this to prevent the session from being flushed when we modify the docker tracker
            docker_tracker = DockerChallengeTracker.query.all()
            # print(type(docker_tracker[0]))
            for i in docker_tracker:
                if is_teams_mode():
                    name = Teams.query.filter_by(id=i.team_id).first()
                    i.team_id = name.name
                else:
                    name = Users.query.filter_by(id=i.user_id).first()
                    i.user_id = name.name
        return render_template("admin_docker_status.html", dockers=docker_tracker)

    app.register_blueprint(admin_docker_status)


kill_container = Namespace("nuke", description="Endpoint to nuke containers")


@kill_container.route("", methods=["POST", "GET"])
class KillContainerAPI(Resource):
    @authed_only
    def get(self):
        if is_admin():
            docker_tracker = DockerChallengeTracker.query.all()
        elif is_teams_mode():
            session = get_current_team()
            docker_tracker = DockerChallengeTracker.query.filter_by(team_id=session.id)
        else:
            session = get_current_user()
            docker_tracker = DockerChallengeTracker.query.filter_by(user_id=session.id)
        container = request.args.get("container")
        full = request.args.get("all")
        docker_config = DockerConfig.query.filter_by(id=1).first()
        if full == "true":
            for c in docker_tracker:
                delete_container(docker_config, c.instance_id)
                DockerChallengeTracker.query.filter_by(
                    instance_id=c.instance_id
                ).delete()
                db.session.commit()

        elif container != "null" and container in [
            c.instance_id for c in docker_tracker
        ]:
            delete_container(docker_config, container)
            DockerChallengeTracker.query.filter_by(instance_id=container).delete()
            db.session.commit()

        else:
            return False
        return True


def create_container(playbook_name: str, deploy_parameters: dict[str, Any]):
    config = DockerConfig.query.filter_by(id=1).first()

    deploy_url = urljoin(config.deployer_url, "/deploy/")
    res = requests.post(
        deploy_url,
        json={
            "playbook_name": playbook_name,
            "parameters": deploy_parameters,
        },
        headers={"Authorization": f"Bearer {config.deployer_secret}"},
    )

    if res.status_code != 200:
        abort(500, "Error communicating with the Docker Deployer")

    return res.json()


def delete_container(deploy_id: int):
    config = DockerConfig.query.filter_by(id=1).first()

    delete_url = urljoin(config.deployer_url, f"/deploy/{deploy_id}/")
    res = requests.delete(
        delete_url,
        headers={"Authorization": f"Bearer {config.deployer_secret}"},
    )

    if res.status_code != 200:
        abort(500, "Error communicating with the Docker Deployer")


# API
container_namespace = Namespace(
    "container", description="Endpoint to interact with containers"
)

class ContainerCreate(BaseModel):
    challenge_id: int


@container_namespace.route("", methods=["POST", "GET"])
class ContainerAPI(Resource):
    @authed_only
    @validate_args(ContainerCreate, location="json")
    def post(self, args: dict):
        challenge: DockerChallenge = DockerChallengeType.challenge_model.query.filter_by(
            id=args["challenge_id"]
        ).first()
        if not challenge:
            abort(400, "Invalid challenge ID")

        name = hashlib.md5(cast(Users, get_current_user()).email.encode()).hexdigest()[:10]
        deploy_parameters = json.loads(challenge.deploy_parameters)
        deploy_parameters["user_name"] = name

        res = create_container(challenge.playbook_name, deploy_parameters)
        deploy_id = res.get("id")
        connection_info = res.get("connection_info")

        instance = DockerChallengeTracker(
            team_id=get_current_team().id if is_teams_mode() else None,
            user_id=get_current_user().id if not is_teams_mode() else None,
            challenge_id=challenge.id,
            deploy_id=deploy_id,
            connection_info=connection_info
        )
        db.session.add(instance)
        db.session.commit()

        return {"success": True, "data": {"id": instance.id, "connection_info": connection_info}}



active_docker_namespace = Namespace(
    "docker", description="Endpoint to retrieve User Docker Image Status"
)


@active_docker_namespace.route("", methods=["POST", "GET"])
class DockerStatus(Resource):
    """
    The Purpose of this API is to retrieve a public JSON string of all docker containers
    in use by the current team/user.
    """

    @authed_only
    def get(self):
        docker = DockerConfig.query.filter_by(id=1).first()
        if is_teams_mode():
            session = get_current_team()
            tracker = DockerChallengeTracker.query.filter_by(team_id=session.id)
        else:
            session = get_current_user()
            tracker = DockerChallengeTracker.query.filter_by(user_id=session.id)
        data = list()
        for i in tracker:
            data.append(
                {
                    "id": i.id,
                    "team_id": i.team_id,
                    "user_id": i.user_id,
                    "docker_image": i.docker_image,
                    "timestamp": i.timestamp,
                    "revert_time": i.revert_time,
                    "instance_id": i.instance_id,
                    "ports": i.ports.split(","),
                    "host": str(docker.hostname).split(":")[0],
                }
            )
        return {"success": True, "data": data}


docker_namespace = Namespace("docker", description="Endpoint to retrieve dockerstuff")


@docker_namespace.route("", methods=["POST", "GET"])
class DockerAPI(Resource):
    """
    This is for creating Docker Challenges. The purpose of this API is to populate the Docker Image Select form
    object in the Challenge Creation Screen.
    """

    @admins_only
    def get(self):
        docker = DockerConfig.query.filter_by(id=1).first()
        images = get_repositories(docker, tags=True, repos=docker.repositories)
        if images:
            data = list()
            for i in images:
                data.append({"name": i})
            return {"success": True, "data": data}
        else:
            return {
                "success": False,
                "data": [{"name": "Error in Docker Config!"}],
            }, 400


def load(app):
    app.db.create_all()
    CHALLENGE_CLASSES["docker"] = DockerChallengeType
    register_plugin_assets_directory(app, base_path="/plugins/docker_challenges/assets")
    define_docker_admin(app)
    define_docker_status(app)
    CTFd_API_v1.add_namespace(docker_namespace, "/docker")
    CTFd_API_v1.add_namespace(container_namespace, "/container")
    CTFd_API_v1.add_namespace(active_docker_namespace, "/docker_status")
    CTFd_API_v1.add_namespace(kill_container, "/nuke")
