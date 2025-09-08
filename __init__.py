from CTFd.api import CTFd_API_v1
from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES

from .api.deploy import deploy_namespace
from .models.challenge_type import AnsibleChallengeType
from .views.admin_config import define_ansible_admin
from .views.admin_view import define_ansible_status


def load(app):
    app.db.create_all()
    CHALLENGE_CLASSES["ansible"] = AnsibleChallengeType
    register_plugin_assets_directory(
        app, base_path="/plugins/ansible_challenges/assets"
    )
    define_ansible_admin(app)
    define_ansible_status(app)
    CTFd_API_v1.add_namespace(deploy_namespace, "/deploy")
