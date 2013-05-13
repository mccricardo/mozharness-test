# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

class config inherits config::base {
    $org = "moco"

    $puppet_notif_email = "releng-shared@mozilla.com"
    $puppet_server_reports = "tagmail,http"
    $puppet_server_reporturl = "http://puppetdash.pvt.build.mozilla.org/reports/upload"
    $builder_username = "servobld"
    $use_random_order = false
    $puppet_server = "puppet"
    $puppet_servers = [
        "servo-puppet1.srv.servo.releng.use1.mozilla.com",
    ]
    $data_servers = $puppet_servers
    $nrpe_allowed_hosts = "10.2.71.20,10.12.75.9,127.0.0.1,10.26.75.30"
    $ntp_server = "ntp.build.mozilla.org"
    $global_authorized_keys = [
        "armenzg",
        "arr",
        "asasaki",
        "banderson",
        "bhearsum",
        "callek",
        "catlee",
        "coop",
        "dustin",
        "hwine",
        "jhopkins",
        "jmoffitt",
        "joduinn",
        "jwatkins",
        "kmoir",
        "mgervasini",
        "nthomas",
        "pmoore",
        "rail",
        "sbruno",
        "zandr",
    ]
    $buildbot_mail_to = "release@mozilla.com"
    $bors_servo_repo_owner = "bhearsum"
    $bors_servo_repo = "servo"
    $bors_servo_reviewers = ["brson", "pcwalton", "metajack", "ILyoan", "jdm", "yichoi", "aydinkim", "sfowler"]
    $bors_servo_builders = ["linux", "mac"] # FIXME after we know exactly what the builders will be called.
    $bors_servo_buildbot_url = "http://buildbot-master-servo1.srv.servo.releng.use1.mozilla.com:8001"
}
