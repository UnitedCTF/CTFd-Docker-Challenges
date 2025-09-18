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
        error = res.json().get('detail', {})
        if isinstance(error, str):
            raise RuntimeError(f"Error during deployment: {error}")
        raise RuntimeError(f"Error during deployment. Deployment id: {res.json().get('detail', {}).get('id', -1)}")

    return res.json()


def delete_container(config: AnsibleConfig, deploy_id: int):
    delete_url = urljoin(config.deployer_url, f"/deploy/{deploy_id}")
    requests.delete(
        delete_url,
        headers={"Authorization": f"Bearer {config.deployer_secret}"},
    )


# API
deploy_namespace = Namespace(
    "deploy", description="Endpoint to interact with deployments"
)


class DeploymentGet(BaseModel):
    challenge_id: Optional[int] = None


class DeploymentCreate(BaseModel):
    challenge_id: int


class DeploymentDelete(BaseModel):
    instance_id: Optional[int] = None


class DeploymentInfo(BaseModel):
    id: int
    challenge_id: int
    connection_info: Optional[str]
    in_progress: bool


@deploy_namespace.route("", methods=["POST", "GET", "DELETE"])
class DeploymentAPI(Resource):
    @authed_only
    @validate_args(DeploymentGet, location="query")
    def get(self, args: dict):
        instances = DeploymentInstance.query.filter_by(
            user_or_team_id=get_current_team().id
            if is_teams_mode()
            else get_current_user().id
        ).filter_by()

        if args.get("challenge_id"):
            instance = instances.filter_by(challenge_id=args["challenge_id"]).first()
            return (
                DeploymentInfo.parse_obj(instance.__dict__).dict() if instance else None
            )

        return [
            DeploymentInfo.parse_obj(instance.__dict__).dict() for instance in instances
        ]

    @authed_only
    @validate_args(DeploymentCreate, location="json")
    def post(self, args: dict):
        challenge: AnsibleChallenge = AnsibleChallenge.query.filter_by(
            id=args["challenge_id"]
        ).first()
        if not challenge:
            fail(400, "Invalid challenge ID")

        existing_instance = DeploymentInstance.query.filter_by(
            user_or_team_id=get_current_team().id
            if is_teams_mode()
            else get_current_user().id,
            challenge_id=challenge.id,
        ).first()
        if existing_instance:
            if existing_instance.in_progress:
                fail(400, "A deployment is already in progress for this challenge")
            return DeploymentInfo.parse_obj(existing_instance.__dict__).dict()

        name = hashlib.md5(cast(Users, get_current_user()).email.encode()).hexdigest()[
            :10
        ]
        deploy_parameters = json.loads(challenge.deploy_parameters)
        deploy_parameters["user_name"] = name

        instance = DeploymentInstance(
            user_or_team_id=get_current_team().id
            if is_teams_mode()
            else get_current_user().id,
            challenge_id=challenge.id,
        )
        db.session.add(instance)
        db.session.commit()

        try:
            res = create_deployment(challenge.playbook_name, deploy_parameters)
            deploy_id = res.get("id")
            connection_info = res.get("connection_info")

            instance.deploy_id = deploy_id
            instance.connection_info = connection_info
            instance.in_progress = False
            db.session.add(instance)
            db.session.commit()
        except Exception as e:
            db.session.delete(instance)
            db.session.commit()
            fail(500, str(e))

        return DeploymentInfo(
            id=instance.id,
            challenge_id=instance.challenge_id,
            connection_info=instance.connection_info,
            in_progress=instance.in_progress,
        ).dict()

    @authed_only
    @validate_args(DeploymentDelete, location="json")
    def delete(self, args: dict):
        instance_id = args.get("instance_id")

        if is_admin():
            instances = DeploymentInstance.query.all()
        else:
            instances = DeploymentInstance.query.filter_by(
                user_or_team_id=get_current_team().id
                if is_teams_mode()
                else get_current_user().id
            )

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
