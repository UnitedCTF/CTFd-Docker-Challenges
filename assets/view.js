CTFd._internal.challenge.data = undefined

CTFd._internal.challenge.renderer = null;

CTFd._internal.challenge.preRender = function () { }

CTFd._internal.challenge.render = function (markdown) {

    return CTFd._internal.challenge.renderer.render(markdown)
}

String.prototype.format = function () {
    const args = arguments;
    return this.replace(/{([0-9]+)}/g, function (match, index) {
        return typeof args[index] == 'undefined' ? match : args[index];
    });
};

CTFd._internal.challenge.postRender = function () {
    get_docker_status();
}


CTFd._internal.challenge.submit = function (preview) {
    var challenge_id = parseInt(CTFd.lib.$('#challenge-id').val())
    var submission = CTFd.lib.$('#challenge-input').val()

    var body = {
        'challenge_id': challenge_id,
        'submission': submission,
    }
    var params = {}
    if (preview) {
        params['preview'] = true
    }

    return CTFd.api.post_challenge_attempt(params, body).then(function (response) {
        if (response.status === 429) {
            // User was ratelimited but process response
            return response
        }
        if (response.status === 403) {
            // User is not logged in or CTF is paused.
            return response
        }
        return response
    })
};

function setDockerContainerHtml(htmlContent) {
    const challengeId = CTFd._internal.challenge.data.id;
    CTFd.lib.$(`#docker_container_${challengeId}`).html(htmlContent);
}

function displayConnectionInfo(deploymentInfo) {
    if (deploymentInfo.in_progress) {
        setSpinningWheel();
        // Poll every 2 seconds until deployment is complete
        setTimeout(get_docker_status, 2000);
        return;
    }

    // If connection_info is a URL, make it a clickable link
    const connectionInfo = (deploymentInfo.connection_info.indexOf('http') === 0) ? `<a href="${deploymentInfo.connection_info}" target="_blank">${deploymentInfo.connection_info}</a>` : `<code>${deploymentInfo.connection_info}</code>`;

    setDockerContainerHtml(
        '<div>Instance available at:<br />' + connectionInfo + '</div>' +
        `<div class="mt-2"><a onclick="check_nuke_container(${deploymentInfo.id})" data-bs-theme='dark' class='btn btn-danger border border-white'><small style='color:white;'><i class="fas fa-trash me-1"></i>Delete Instance</small></a></div>`
    );
}

function setSpinningWheel() {
    setDockerContainerHtml('<div class="text-center"><i class="fas fa-circle-notch fa-spin fa-1x"></i></div>');
}

function resetDeployButton() {
    setDockerContainerHtml(`<span><a onclick="deploy()" class='btn btn-dark border border-white'><small style='color:white;'><i class="fas fa-play me-1"></i>Deploy Instance</small></a></span>`);
}

function showErrorMessage(title, body) {
    const content =
        '<div>' +
        '<h5>' + title + '</h5>' +
        '<p>' + body + '</p>' +
        '</div>';

    setDockerContainerHtml(content);
}

async function get_docker_status() {
    const challengeId = CTFd._internal.challenge.data.id;

    const data = await CTFd.fetch("/api/v1/deploy?challenge_id=" + challengeId)
        .then((data) => {
            return data.json();
        });

    if (data) {
        displayConnectionInfo(data);
    }
    return;
}

async function deploy() {
    let res;
    try {
        setSpinningWheel();
        res = await CTFd.fetch("/api/v1/deploy", {
            method: "POST",
            body: JSON.stringify({
                challenge_id: CTFd._internal.challenge.data.id,
            }),
            headers: {
                "Content-Type": "application/json"
            }
        });
    } catch (err) {
        showErrorMessage("Attention!", "Network error while starting container.");
        return;
    }

    if (!res.ok) {
        const error = await res.json();
        const errorMessage = JSON.parse(error.message || "{}");
        if (errorMessage.message === "A deployment is already in progress for this challenge") {
            // If a deployment is already in progress, poll for status
            setSpinningWheel();
            setTimeout(get_docker_status, 2000);
            return;
        }

        showErrorMessage("Attention!", errorMessage.message || "Error starting container.");
        return;
    }

    const data = await res.json();

    displayConnectionInfo(data);
}

function check_nuke_container(instance_id) {
    if (confirm("Are you sure you want to nuke this container?")) {
        nuke_container(instance_id);
    }
}

function nuke_container(instance_id) {
    setSpinningWheel();
    CTFd.fetch("/api/v1/deploy", {
        method: "DELETE",
        body: JSON.stringify({
            instance_id: instance_id,
        }),
        headers: {
            "Content-Type": "application/json"
        }
    })
        .then(() => {
            resetDeployButton();
        }).catch(() => {
            showErrorMessage("Attention!", "Error nuking container.");
        });
}
