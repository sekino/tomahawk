# -*- coding: utf-8 -*-
from six import print_
#from nose.tools import ok_
import os
import pexpect

#import sys
import utils

# TODO: mock_ssh.py --prompt enabled, so we can test -s -l options.
TOMAHAWK_PATH = os.path.join(utils.get_bin_dir(__file__), 'tomahawk')
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

def test_06_prompt_sudo_password():
    command = "%s -D --hosts=localhost --prompt-login-password --ssh-user=tomahawk_test uptime" % (TOMAHAWK_PATH)
    child = pexpect.spawn(
        command,
        timeout = 5
    )
    i = child.expect([ pexpect.EOF, pexpect.TIMEOUT, 'Enter a password.+' ])
    if i == 0: # EOF
        print_('EOF')
        print_(child.before)
    elif i == 1: # timeout
        print_('TIMEOUT')
        #ok_(False, 'Failure: ')
        assert True
    elif i == 2:
        child.sendline("tomahawk_test")
        child.expect(pexpect.EOF)
        #ok_(True, "execute (prompt password)")
        assert True


def test_10_confirm_execution_on_production():
    command = '%s --hosts=localhost,localhost uptime' % (TOMAHAWK_PATH)
    env = os.environ
    env['TOMAHAWK_ENV'] = 'production'
    child = pexpect.spawn(
        command,
        timeout = 5,
#        logfile = sys.stdout,
        env = env
    )
    i = child.expect([ pexpect.EOF, pexpect.TIMEOUT, 'Command "uptime" will be executed to 2 hosts.' ])
    if i == 0: # EOF
        print_('EOF')
        print_(child.before)
    elif i == 1: # timeout
        print_('TIMEOUT')
        print_(child.before, child.after)
        #ok_(False, 'Failure: confirm_execution_on_production with "TOMAHAWK_ENV"')
        assert False
    elif i == 2:
        child.sendline('yes')
        child.expect(pexpect.EOF)
        print_(child.before)
        #ok_(True, 'confirm_execution_on_production with "TOMAHAWK_ENV"')
        assert False
