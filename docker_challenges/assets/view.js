CTFd._internal.challenge.data = undefined

CTFd._internal.challenge.data = undefined;

CTFd._internal.challenge.renderer = null;


CTFd._internal.challenge.preRender = function() {}

CTFd._internal.challenge.render = function(markdown) {

    return CTFd._internal.challenge.renderer.render(markdown)
}

String.prototype.format = function () {
  const args = arguments;
  return this.replace(/{([0-9]+)}/g, function (match, index) {     
    return typeof args[index] == 'undefined' ? match : args[index];
  });
};

CTFd._internal.challenge.postRender = function() {}


CTFd._internal.challenge.submit = function(preview) {
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

    return CTFd.api.post_challenge_attempt(params, body).then(function(response) {
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

                CTFd.lib.$.each(result['data'], function(i, item) {
                    if (item.docker_image === container) {
                        containerFound = true;
                        const ports = String(item.ports).split(',');
                        let data = '';
                        CTFd.lib.$.each(ports, function(x, port) {
                            port = String(port).split('/')[0];
                            data = data + `<a href='http://${hostname}:${port}' target='_blank'>http://${hostname}:${port}</a><br />`;
                        });
                        CTFd.lib.$('#docker_container').html('<pre>Instance available at:<br />' + data + '<div class="mt-2" id="' + String(item.instance_id).substring(0,10) + '_revert_container"></div>');
                        const countDownDate = new Date(parseInt(item.revert_time) * 1000).getTime();
                        const x = setInterval(function() {
                            const now = new Date().getTime();
                            const distance = countDownDate - now;
                            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                            let seconds = Math.floor((distance % (1000 * 60)) / 1000);
                            if (seconds < 10) {
                                seconds = "0" + seconds;
                            }
                            CTFd.lib.$("#" + String(item.instance_id).substring(0,10) + "_revert_container").html('Next Revert Available in ' + minutes + ':' + seconds);
                            if (distance < 0) {
                                clearInterval(x);
                                CTFd.lib.$("#" + String(item.instance_id).substring(0,10) + "_revert_container").html('<a onclick="start_container(\'' + item.docker_image + '\', true);" class=\'btn btn-dark\'><small style=\'color:white;\'><i class="fas fa-redo"></i> Revert</small></a>');
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

function start_container(container, revert=false) {
    get_docker_status(container)
        .then((docker_status) => {
            if (revert === true || docker_status !== true) {
                CTFd.lib.$('#docker_container').html('<div class="text-center"><i class="fas fa-circle-notch fa-spin fa-1x"></i></div>');
                CTFd.fetch("/api/v1/container?name=" + container)
                    .then(() => {
                        get_docker_status(container);
                    }).catch(() => {
                        ezal("Attention!", "You can only revert a container once per 5 minutes! Please be patient.");
                        get_docker_status(container);
                    });
            }
        });
}

function ezal(title, body) {
    const content =
        '<div>' +
        '<h5>' + title + '</h5>' +
        '<p>' + body + '</p>' +
        '</div>';

    CTFd.lib.$("#docker_container").html(content);
}