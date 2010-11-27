# -*- coding: utf-8 -*-
from getpass import getuser
from multiprocessing import Pool
from os import path
from sys import stderr
from time import sleep
from tomahawk.constants import DEFAULT_RSYNC_OPTIONS
from tomahawk.expect import CommandWithExpect
from tomahawk.utils import read_login_password, read_sudo_password

def _command(command, login_password, sudo_password, expect_timeout):
    #print '_command() :' + command
#    if login_password is not None or sudo_password is not None:
    return CommandWithExpect(command, login_password, sudo_password, expect_timeout).execute()

def _rsync(command, login_password, expect_timeout):
    return CommandWithExpect(command, login_password, None, expect_timeout).execute()

class BaseExecutor(object):
    """
    """
    
    def __init__(self, context, log, hosts=[], **kwargs):
        """
        """
        if context is None:
            raise RuntimeError('Argument "context" required.')
        if len(hosts) == 0:
            raise RuntimeError('Argument "hosts" length must be > 0')

        options = context.options

        newline = False
        login_password = None
        if 'login_password' in kwargs:
            login_password = kwargs['login_password']
        elif options.prompt_login_password:
            login_password = read_login_password()
            newline = True
        
        sudo_password = None
        if 'sudo_password' in kwargs:
            sudo_password = kwargs['sudo_password']
        elif options.__dict__.get('prompt_sudo_password') \
                or (context.arguments is not None and context.arguments[0].startswith('sudo')):
            sudo_password = read_sudo_password()
            newline = True

        if newline:
            print

        self.context = context
        self.log = log
        self.hosts = hosts
        self.login_password = login_password
        self.sudo_password = sudo_password
        self.raise_error = False if options.continue_on_error else True
        self.process_pool = None

    def initialize_process_pool(self, parallel=1):
        if self.process_pool is None:
            self.process_pool = Pool(processes=parallel)

    def execute_ssh_command(self, command, login_password, sudo_password, expect_timeout):
        return self.process_pool.apply_async(
            _command,
            [ command, login_password, sudo_password, expect_timeout ]
        ).get(timeout = expect_timeout)

    def execute_rsync_command(self, command, login_password, expect_timeout):
        return self.process_pool.apply_async(
            _rsync,
            [ command, login_password, expect_timeout ]
        ).get(timeout = expect_timeout)

    def __del__(self):
        if self.process_pool is not None:
            self.process_pool.close()


class CommandExecutor(BaseExecutor):
    def execute(self, commands):
        if len(commands) == 0:
            raise RuntimeError('1st argument "commands" length is 0')

        options = self.context.options
        ssh_user = options.ssh_user or getuser()
        ssh_options = options.ssh_options or ''
        ssh_options += '-l ' + ssh_user
        self.initialize_process_pool(options.parallel)

        error_hosts = []
        for host in self.hosts:
            for command in commands:
                # execute a command with shell because we want to use pipe(|) and so on.
                c = 'ssh %s %s "/bin/sh -c \'%s\'"' % (ssh_options, host, command)
                # host, command, ssh_user, ssh_option, login_password, sudo_password
                exit_status, command_output = self.execute_ssh_command(
                    c, self.login_password, self.sudo_password, options.expect_timeout
                )

                output_params = {
                    'user': ssh_user,
                    'host': host,
                    'command': command,
                    'output': command_output
                }
                # output template
                # TODO: specify from command line option
                output = '%(user)s@%(host)s %% %(command)s\n%(output)s' % output_params
                if exit_status == 0:
                    print output, '\n'
                else:
                    output += '[error] Command failed ! (status = %d)' % exit_status
                    print output, '\n'
                    error_hosts.append(host)
                    if self.raise_error:
                        #raise RuntimeError("[error] Command '%s' failed on host '%s'" % (command, host))
                        print >> stderr, '[error] Command "%s" failed on host "%s"' % (command, host)
                        return 1

            if options.delay != 0:
                sleep(options.delay)

        if len(error_hosts) != 0:
            hosts = ''
            for h in error_hosts:
                hosts += '  %s\n' % (h)
            hosts = hosts.rstrip()
            print >> stderr, '[error] Command "%s" failed on following hosts\n%s' % (command, hosts)
            return 1
        
        return 0

class RsyncExecutor(BaseExecutor):
    # TODO: test
    def execute(self, source, destination):
        if source is None:
            raise RuntimeError('1st argument "source" must not be None')
        if destination is None:
            raise RuntimeError('2nd argument "destination" must not be None')

        options = self.context.options
        rsync_user = options.rsync_user or getuser()
        rsync_options = options.rsync_options or DEFAULT_RSYNC_OPTIONS
        mirror_mode = options.mirror_mode or 'push'
        if mirror_mode not in ('push', 'pull'):
            raise RuntimeError('Invalid mirror_mode: ' + mirror_mode)

        self.initialize_process_pool(options.parallel)

        rsync_template = ''
        if mirror_mode == 'push':
            rsync_template = 'rsync %s %s %s@%%s:%s' % (
                rsync_options,
                source,
                rsync_user,
                destination,
            )
        else:
            rsync_template = 'rsync %s %s@%%s:%s %%s' % (
                rsync_options,
                rsync_user,
                source,
            )

        error_hosts = []
        for host in self.hosts:
            c = ''
            if mirror_mode == 'push':
                c = rsync_template % (host)
            else: # pull
                if options.append_host_suffix:
                    if path.exists(destination):
                        if path.isdir(destination):
                            # if destination is a directory, gets a source filename and appends a host suffix
                            file_name = path.basename(source)
                            if not destination.endswith('/'):
                                destination += '/'
                            destination += '%s__%s' % (file_name, host)
                        else:
                            # if destination is a file, simply appends a host suffix
                            destination += '__' + host
                    else:
                        # if file doesn't exist
                        destination += '__' + host
                c = rsync_template % (host, destination)
                
            self.log.debug('command = "%s"' % (c))
            exit_status, command_output = self.execute_rsync_command(
                c, self.login_password, options.expect_timeout
            )
            output = '%% %s\n%s' % (c, command_output)
            if exit_status == 0:
                print output, '\n'
            else:
                output += '[error] rsync failed ! (status = %d)' % exit_status
                print output, '\n'
                error_hosts.append(host)
                if self.raise_error:
                    #raise RuntimeError("[error] '%s' failed on host '%s'" % (command, host))
                    print >> stderr, '[error] "%s" failed on host "%s"' % (c, host)
                    return 1
                
            if options.delay != 0:
                sleep(options.delay)

            if len(error_hosts) != 0:
                hosts = ''
                for h in error_hosts:
                    hosts += '  %s\n' % (h)
                hosts.rstrip()
                print >> stderr, '[error] "%s" failed on following hosts\n%s' % (c, hosts)
                return 1

        return 0
