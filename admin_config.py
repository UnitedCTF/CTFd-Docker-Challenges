from flask import Blueprint, request, render_template
from wtforms import (
    HiddenField,
    StringField,
)

from CTFd.forms import BaseForm
from CTFd.forms.fields import SubmitField
from CTFd.models import db
from CTFd.utils.decorators import (
    admins_only,
)


class DockerConfig(db.Model):
    """
    Docker Config Model. This model stores the config for docker API connections.
    """

    id = db.Column(db.Integer, primary_key=True)
    deployer_url = db.Column("deployer_url", db.String(255))
    deployer_secret = db.Column("deployer_secret", db.String(255))


class DockerConfigForm(BaseForm):
    id = HiddenField()
    deployer_url = StringField(
        "Deployer URL", description="The full URL to the Docker Deployer Service"
    )
    deployer_secret = StringField(
        "Deployer Secret",
        description="The secret used to authenticate with the Deployer",
    )
    submit = SubmitField("Submit")


def define_docker_admin(app):
    admin_docker_config = Blueprint(
        "admin_docker_config",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )

    @admin_docker_config.route("/admin/docker_config", methods=["GET", "POST"])
    @admins_only
    def docker_config():
        config = DockerConfig.query.filter_by(id=1).first()
        if not config:
            config = DockerConfig()

        form = DockerConfigForm(request.form, config)

        if request.method == "POST" and form.validate():
            form.populate_obj(config)

            db.session.add(config)
            db.session.commit()

        return render_template(
            "docker_config.html", form=form
        )

    app.register_blueprint(admin_docker_config)
