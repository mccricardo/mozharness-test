# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# the keys in this file are documented in
#   https://wiki.mozilla.org/ReleaseEngineering/PuppetAgain#Config
# if you add a new key here, add it to the wiki as well!

# the keys in this file are documented in
#   https://wiki.mozilla.org/ReleaseEngineering/PuppetAgain#Config
# if you add a new key here, add it to the wiki as well!

# This class is overridden by the org-specific config symlinked from manifests/config.pp

class config::base {
    $org = undef

    $puppet_notif_email = "nobody@mozilla.com"
    $data_server = "repos"
    $data_servers = [$data_server]
    $puppet_servers = "puppet"
    $puppet_server = [$puppet_servers]
    $use_random_order = false # TODO: remove in 3.2.0 rollout
    $builder_username = 'cltbld'
    $nrpe_allowed_hosts = '127.0.0.1'
    $ntp_server = "pool.ntp.org"
    $relay_domains = "smtp.mozilla.org"
    $crl_sync_url= ""
    $puppet_again_repo = "http://hg.mozilla.org/build/puppet"
    $global_authorized_keys = ""
    $puppet_server_reports = "tagmail"
    $puppet_server_reporturl = "http://localhost:3000/reports/upload"
    $master_json = "https://hg.mozilla.org/build/tools/raw-file/default/buildfarm/maintenance/production-masters.json"
    $buildbot_tools_hg_repo = "https://hg.mozilla.org/build/tools"
    $buildbot_configs_hg_repo = "https://hg.mozilla.org/build/buildbot-configs"
    $buildbot_configs_branch = "production"
    $buildbot_mail_to = "nobody@mozilla.com"
}