# cltbld.pp
# refactored and cleaned up - 

class cltbld {

    File{ mode => 644, owner => cltbld, group => cltbld }

    #################################################
	# Manage the cltbld user:group
    #################################################
	user { "cltbld":
		ensure => 'present',
		name => "cltbld",
		uid => 500,
		gid => 500,
		comment => "Client Builder Puppet Test",
		managehome => true,
		home => $operatingsystem ? {
                    default => "/home/cltbld",
                },
		shell => "/bin/bash",
		provider => 'useradd',
		password => "i don't think so"
	}

	group { "cltbld":
		ensure => 'present',
		name => "cltbld",
		provider => 'groupadd',
		gid => 500;
	}

    #################################################
	# Manage cltbld user files
    #################################################
	file { 
            "/home/cltbld/.bash_profile":
		source => "${universalhome}cltbld/.bash_profile";

            "/home/cltbld/crontab":
                source => "${universalhome}cltbld/crontab";

	    "/home/cltbld/.vnc":
		mode => 775,
		ensure => directory;

	    "/home/cltbld/.vnc/passwd":
		mode => 600,
		source => "${universalhome}cltbld/.vnc/passwd";

	    "/home/cltbld/.vnc/xstartup":
		mode => 700,
		source => "${universalhome}cltbld/.vnc/xstartup";
        }

        exec { "/usr/bin/crontab -u cltbld /home/cltbld/crontab":
                subscribe => File["/home/cltbld/crontab"];
        }
}
