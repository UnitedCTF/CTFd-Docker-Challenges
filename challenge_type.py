import json
from typing import Any

from flask import Blueprint

from CTFd.models import (
    Challenges,
    db,
)
from CTFd.plugins.challenges import BaseChallenge


class DockerChallenge(Challenges):
    __mapper_args__ = {"polymorphic_identity": "docker"}
    id = db.Column(None, db.ForeignKey("challenges.id"), primary_key=True)
    playbook_name = db.Column(db.String(255), index=True)
    deploy_parameters = db.Column(db.Text, default="{}")

    def __init__(self, playbook_name: str, deploy_parameters: str, *args, **kwargs):
        self.playbook_name = playbook_name
        self.deploy_parameters = deploy_parameters
        kwargs["type"] = "docker"
        super().__init__(*args, **kwargs)

class DockerChallengeType(BaseChallenge):
    id = "docker"
    name = "docker"
    templates = {
        "create": "/plugins/docker_challenges/assets/create.html",
        "update": "/plugins/docker_challenges/assets/update.html",
        "view": "/plugins/docker_challenges/assets/view.html",
    }
    scripts = {
        "create": "/plugins/docker_challenges/assets/create.js",
        "update": "/plugins/docker_challenges/assets/update.js",
        "view": "/plugins/docker_challenges/assets/view.js",
    }
    route = "/plugins/docker_challenges/assets"
    blueprint = Blueprint(
        "docker_challenges",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )
    challenge_model = DockerChallenge

    @classmethod
    def delete(cls, challenge):
        """
        This method is used to delete the resources used by a challenge.
        FIXME: Will need to kill all containers here

        :param challenge:
        :return:
        """
        super().delete(challenge)

    @classmethod
    def read(cls, challenge):
        """
        This method is in used to access the data of a challenge in a format processable by the front end.

        :param challenge:
        :return: Challenge object, data dictionary to be returned to the user
        """
        challenge = DockerChallenge.query.filter_by(id=challenge.id).first()
        data = super().read(challenge)
        data.update(
            {
                "playbook_name": challenge.playbook_name,
                "deploy_parameters": challenge.deploy_parameters,
            }
        )
        return data

    @classmethod
    def solve(cls, user, team, challenge, request):
        """
        This method is used to insert Solves into the database in order to mark a challenge as solved.

        :param team: The Team object from the database
        :param chal: The Challenge object from the database
        :param request: The request the user submitted
        :return:
        """

        # FIXME: Delete containers

        return super().solve(user, team, challenge, request)
