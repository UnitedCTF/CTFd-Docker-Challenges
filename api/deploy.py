import hashlib
import json
from typing import Any, Optional, cast
from urllib.parse import urljoin

import requests
from flask import abort
from flask_restx import Namespace, Resource
from pydantic import BaseModel

from CTFd.api.v1.helpers.request import validate_args
from CTFd.models import Users, db
from CTFd.plugins.ansible_challenges.models.challenge_type import AnsibleChallenge
from CTFd.plugins.ansible_challenges.models.deployment_instance import (
    DeploymentInstance,
)
from CTFd.plugins.ansible_challenges.views.admin_config import AnsibleConfig
from CTFd.utils.config import is_teams_mode
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_team, get_current_user, is_admin


def fail(error_code: int, message: str):
    abort(error_code, json.dumps({"message": message}))


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
        fail(500, f"Error communicating with the Ansible Deployer. Detailed error: {res.text}")

    return res.json()


def delete_container(config: AnsibleConfig, deploy_id: int):
    delete_url = urljoin(config.deployer_url, f"/deploy/{deploy_id}/")
    res = requests.delete(
        delete_url,
        headers={"Authorization": f"Bearer {config.deployer_secret}"},
    )

    if res.status_code != 200:
        fail(500, f"Error communicating with the Ansible Deployer. Detailed error: {res.text}")


# API
deploy_namespace = Namespace(
    "deploy", description="Endpoint to interact with deployments"
)


class DeploymentCreate(BaseModel):
    challenge_id: int


class DeploymentDelete(BaseModel):
    instance_id: Optional[int] = None


class DeploymentInfo(BaseModel):
    id: int
    challenge_id: int
    connection_info: dict[str, Any]


@deploy_namespace.route("", methods=["POST", "GET", "DELETE"])
class DeploymentAPI(Resource):
    @authed_only
    def get(self):
        if is_teams_mode():
            session = get_current_team()
            instances = DeploymentInstance.query.filter_by(team_id=session.id)
        else:
            session = get_current_user()
            instances = DeploymentInstance.query.filter_by(user_id=session.id)

        return [DeploymentInfo(**instance) for instance in instances]

    @authed_only
    @validate_args(DeploymentCreate, location="json")
    def post(self, args: dict):
        challenge: AnsibleChallenge = AnsibleChallenge.query.filter_by(
            id=args["challenge_id"]
        ).first()
        if not challenge:
            fail(400, "Invalid challenge ID")

        name = hashlib.md5(cast(Users, get_current_user()).email.encode()).hexdigest()[
            :10
        ]
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
            connection_info=connection_info,
        )
        db.session.add(instance)
        db.session.commit()

        return {"id": instance.id, "connection_info": connection_info}

    @authed_only
    @validate_args(DeploymentDelete, location="json")
    def delete(self, args: dict):
        instance_id = args.get("instance_id")

        if is_admin():
            instances = DeploymentInstance.query.all()
        elif is_teams_mode():
            session = get_current_team()
            instances = DeploymentInstance.query.filter_by(team_id=session.id)
        else:
            session = get_current_user()
            instances = DeploymentInstance.query.filter_by(user_id=session.id)

        config = AnsibleConfig.query.filter_by(id=1).first()
        if instance_id is None:
            for instance in instances:
                delete_container(config, instance.deploy_id)
                db.session.delete(instance)
                db.session.commit()
        else:
            instance = next(filter(lambda i: i.id == instance_id, instances), None)
            if instance:
                delete_container(config, instance.deploy_id)
                db.session.delete(instance)
                db.session.commit()
            else:
                fail(403, "You do not have permission to delete this container")

        return "", 204
