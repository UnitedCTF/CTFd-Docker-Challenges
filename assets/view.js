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
    // get_docker_status(challenge.data.docker_image);
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


function get_docker_status(container) {
    return CTFd.fetch("/api/v1/docker_status")
        .then((data) => {
            return data.json().then((result) => {
                const hostname = data.url.split('//')[1].split('/')[0];
                let containerFound = false;

                CTFd.lib.$.each(result['data'], function (i, item) {
                    if (item.docker_image === container) {
                        containerFound = true;
                        const ports = String(item.ports).split(',');
                        let data = '';
                        CTFd.lib.$.each(ports, function (x, port) {
                            port = String(port).split('/')[0];
                            data = data + `<a href='http://${hostname}:${port}' target='_blank'>http://${hostname}:${port}</a><br />`;
                        });
                        CTFd.lib.$('#docker_container').html(
                            '<pre>Instance available at:<br />' + data +
                            '<div class="mt-2" id="' + String(item.instance_id).substring(0, 10) + '_revert_container"></div>' +
                            `<div class="mt-2" id="${String(item.instance_id).substring(0, 10)}_delete_container"><a id="delete_${String(item.instance_id).substring(0, 10)}" style="cursor: pointer;" class="fas fa-trash" onclick="check_nuke_container('${item.instance_id}')"></a></div>`
                        );
                        const countDownDate = new Date(parseInt(item.revert_time) * 1000).getTime();
                        const x = setInterval(function () {
                            const now = new Date().getTime();
                            const distance = countDownDate - now;
                            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                            let seconds = Math.floor((distance % (1000 * 60)) / 1000);
                            if (seconds < 10) {
                                seconds = "0" + seconds;
                            }
                            CTFd.lib.$("#" + String(item.instance_id).substring(0, 10) + "_revert_container").html('Next Revert Available in ' + minutes + ':' + seconds);
                            if (distance < 0) {
                                clearInterval(x);
                                CTFd.lib.$("#" + String(item.instance_id).substring(0, 10) + "_revert_container").html('<a onclick="start_container(\'' + item.docker_image + '\', true);" class=\'btn btn-dark\'><small style=\'color:white;\'><i class="fas fa-redo"></i> Revert</small></a>');
                            }
                        }, 1000);
                    }
                });

                return containerFound;
            }).catch(() => {
                ezal("Attention!", "Error");
                return false;
            });
        }).catch(() => {
            // TODO
            ezal("Attention!", "Error");
            return false;
        });
}

async function deploy() {
    let res;
    try {
        CTFd.lib.$('#docker_container').html('<div class="text-center"><i class="fas fa-circle-notch fa-spin fa-1x"></i></div>');
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
        console.log(err)
        ezal("Attention!", "Network error while starting container.");
        return;
    }

    if (!res.ok) {
        const error = await res.json();
        const errorMessage = JSON.parse(error.message || "{}");
        ezal("Attention!", errorMessage.message || "Error starting container.");
        return;
    }

    const data = await res.json();

    // If connection_info is a URL, make it a clickable link
    const connection_info = (data.connection_info.indexOf('http') === 0) ? `<a href="${data.connection_info}" target="_blank">${data.connection_info}</a>` : `<code>${data.connection_info}</code>`;

    console.log("Container started");
    CTFd.lib.$('#docker_container').html(
        '<div>Instance available at:<br />' + connection_info + '</div>' +
        `<div class="mt-2"><a onclick="check_nuke_container(${data.id})" data-bs-theme='dark' class='btn btn-danger border border-white'><small style='color:white;'><i class="fas fa-trash me-1"></i>Delete Instance</small></a></div>`
    );
}

function ezal(title, body) {
    const content =
        '<div>' +
        '<h5>' + title + '</h5>' +
        '<p>' + body + '</p>' +
        '</div>';

    CTFd.lib.$("#docker_container").html(content);
}

function check_nuke_container(instance_id) {
    if (confirm("Are you sure you want to nuke this container?")) {
        nuke_container(instance_id);
    }
}

function nuke_container(instance_id) {
    CTFd.lib.$('#docker_container').html('<div class="text-center"><i class="fas fa-circle-notch fa-spin fa-1x"></i></div>');
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
            CTFd.lib.$('#docker_container').html(`<span><a onclick="deploy()" class='btn btn-dark border border-white'><small style='color:white;'><i class="fas fa-play me-1"></i>Deploy Instance</small></a></span>`);
        }).catch(() => {
            ezal("Attention!", "Error nuking container.");
        });
}
