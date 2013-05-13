class screenresolution($width, $height, $depth, $refresh) {
    case $::operatingsystem {
        Darwin: {
            # set the screen resolution appropriately
            include packages::mozilla::screenresolution
            $resolution = "${width}x${height}x${depth}@${refresh}"

            # this can't run while puppetizing, since the automatic login isn't in place yet, and
            # the login window does not allow screenresolution to run.
            if (!$puppetizing) {
                exec {
                    "set-resolution":
                        command => "/usr/local/bin/screenresolution set $resolution",
                        unless => "/usr/local/bin/screenresolution get 2>&1 | /usr/bin/grep 'Display 0: $resolution'",
                        require => Class["packages::mozilla::screenresolution"];
                }
            }
        }
        default: {
            fail("Cannot manage screen resolution for $::operatingsystem")
        }
    }
}