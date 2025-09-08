import hashlib
import json
from typing import Any, cast
from urllib.parse import urljoin

from pydantic import BaseModel
import requests
from flask import (
    abort,
    request,
)
from flask_restx import Namespace, Resource

from CTFd.api import CTFd_API_v1
from CTFd.api.v1.helpers.request import validate_args
from CTFd.models import (
    Users,
    db,
)
from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.ansible_challenges.views.admin_view import define_ansible_status
from CTFd.plugins.challenges import CHALLENGE_CLASSES
from CTFd.utils.config import is_teams_mode
from CTFd.utils.decorators import (
    authed_only,
)
from CTFd.utils.user import get_current_team, get_current_user, is_admin

from .views.admin_config import AnsibleConfig, define_ansible_admin
from .models.challenge_type import AnsibleChallenge, AnsibleChallengeType
from .models.deployment_instance import DeploymentInstance


kill_container = Namespace("nuke", description="Endpoint to nuke containers") 

@kill_container.route("", methods=["POST", "GET"])
class KillContainerAPI(Resource):
    @authed_only
    def get(self):
        if is_admin():
            docker_tracker = DeploymentInstance.query.all()
        elif is_teams_mode():
            session = get_current_team()
            docker_tracker = DeploymentInstance.query.filter_by(team_id=session.id)
        else:
            session = get_current_user()
            docker_tracker = DeploymentInstance.query.filter_by(user_id=session.id)
        container = request.args.get("container")
        full = request.args.get("all")
        docker_config = AnsibleConfig.query.filter_by(id=1).first()
        if full == "true":
            for c in docker_tracker:
                delete_container(docker_config, c.instance_id)
                DeploymentInstance.query.filter_by(
                    instance_id=c.instance_id
                ).delete()
                db.session.commit()

        elif container != "null" and container in [
            c.instance_id for c in docker_tracker
        ]:
            delete_container(docker_config, container)
            DeploymentInstance.query.filter_by(instance_id=container).delete()
            db.session.commit()

        else:
            return False
        return True


def create_deployment(playbook_name: str, deploy_parameters: dict[str, Any]):
    config = AnsibleConfig.query.filter_by(id=1).first()

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
        abort(500, "Error communicating with the Ansible Deployer")

    return res.json()


def delete_container(deploy_id: int):
    config = AnsibleConfig.query.filter_by(id=1).first()

    delete_url = urljoin(config.deployer_url, f"/deploy/{deploy_id}/")
    res = requests.delete(
        delete_url,
        headers={"Authorization": f"Bearer {config.deployer_secret}"},
    )

    if res.status_code != 200:
        abort(500, "Error communicating with the Ansible Deployer")


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
        challenge: AnsibleChallenge = AnsibleChallengeType.challenge_model.query.filter_by(
            id=args["challenge_id"]
        ).first()
        if not challenge:
            abort(400, "Invalid challenge ID")

        name = hashlib.md5(cast(Users, get_current_user()).email.encode()).hexdigest()[:10]
        deploy_parameters = json.loads(challenge.deploy_parameters)
        deploy_parameters["user_name"] = name

        res = create_deployment(challenge.playbook_name, deploy_parameters)
        deploy_id = res.get("id")
        connection_info = res.get("connection_info")

        instance = DeploymentInstance(
            team_id=get_current_team().id if is_teams_mode() else None,
            user_id=get_current_user().id if not is_teams_mode() else None,
            challenge_id=challenge.id,
            deploy_id=deploy_id,
            connection_info=connection_info
        )
        db.session.add(instance)
        db.session.commit()

        return {"success": True, "data": {"id": instance.id, "connection_info": connection_info}}



active_ansible_namespace = Namespace(
    "ansible", description="Endpoint to retrieve User Ansible Image Status"
)


@active_ansible_namespace.route("", methods=["POST", "GET"])
class AnsibleStatus(Resource):
    """
    The Purpose of this API is to retrieve a public JSON string of all ansible containers
    in use by the current team/user.
    """

    @authed_only
    def get(self):
        docker = AnsibleConfig.query.filter_by(id=1).first()
        if is_teams_mode():
            session = get_current_team()
            tracker = DeploymentInstance.query.filter_by(team_id=session.id)
        else:
            session = get_current_user()
            tracker = DeploymentInstance.query.filter_by(user_id=session.id)
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


def load(app):
    app.db.create_all()
    CHALLENGE_CLASSES["ansible"] = AnsibleChallengeType
    register_plugin_assets_directory(app, base_path="/plugins/ansible_challenges/assets")
    define_ansible_admin(app)
    define_ansible_status(app)
    CTFd_API_v1.add_namespace(container_namespace, "/container")
    CTFd_API_v1.add_namespace(active_ansible_namespace, "/ansible_status")
    CTFd_API_v1.add_namespace(kill_container, "/nuke")
