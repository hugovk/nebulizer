#!/usr/bin/env python
#
# cli: functions for building command utilities
import sys
import os
import optparse
import getpass
import logging
from nebulizer import get_version
from .core import get_galaxy_instance
from .core import turn_off_urllib3_warnings
from .core import Credentials
import users
import libraries
import tools

logging.basicConfig(format="%(levelname)s %(message)s")

def base_parser(usage=None,description=None):
    """
    Create base parser with common options

    """
    p = optparse.OptionParser(usage=usage,
                              version="%s" % get_version(),
                              description=description)
    p.add_option('-k','--api_key',action='store',dest='api_key',
                 default=None,
                 help="specify API key for GALAXY_URL (otherwise will try to "
                 "look up from .nebulizer file)")
    p.add_option('-u','--username',action='store',dest='username',
                 default=None,
                 help="specify username (i.e. email) to log into Galaxy with")
    p.add_option('-P','--galaxy_password',action='store',
                 dest='galaxy_password',default=None,
                 help="supply password for Galaxy instance")
    p.add_option('-n','--no-verify',action='store_true',dest='no_verify',
                 default=False,help="don't verify HTTPS connections")
    p.add_option('-q','--suppress-warnings',action='store_true',
                 dest='suppress_warnings',
                 default=False,help="suppress warning messages")
    p.add_option('--debug',action='store_true',dest='debug',
                 default=False,help="turn on debugging output")
    return p

def handle_ssl_warnings(verify=True):
    """
    Turn off SSL warnings from urllib3

    Arguments:
      verify (bool): if False then disable the warnings from
        urllib3 about SSL certificate verification

    """
    if not verify:
        logging.warning("SSL certificate verification has "
                        "been disabled")
        turn_off_urllib3_warnings()

def handle_debug(debug=True):
    """
    Turn on debugging output from logging

    Arguments:
      debug (bool): if True then turn on debugging output

    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)

def handle_suppress_warnings(suppress_warnings=True):
    """
    Suppress warning messages output from logging

    Arguments:
      suppress_warnings (bool): if True then turn off
        warning messages

    """
    if suppress_warnings:
        logging.getLogger().setLevel(logging.ERROR)
    else:
        logging.getLogger().setLevel(logging.WARNING)

def handle_credentials(email,password,prompt="Password: "):
    """
    Sort out email and password for accessing Galaxy

    Arguments:
      email (str): Galaxy e-mail address corresponding to the user
      password (str): password of Galaxy account corresponding to
        email address; if None then user will be prompted to
        supply password on the command line
      prompt (str): text to display as password prompt

    Returns:
      Tuple: tuple consisting of (email,password).

    """
    if email is None:
        return (None,None)
    if password is None:
        password = getpass.getpass(prompt)
    return (email,password)

def fetch_api_key(galaxy_url,email,password=None,verify=True):
    """
    Fetch a new API key from a Galaxy instance

    Arguments:
      galaxy_url (str): alias or URL of Galaxy instance to get
        API key for
      email (str): Galaxy e-mail address corresponding to the
        user to fetch API for
      password (str): password of Galaxy account corresponding to
        email address (optional)
      verify (boolean): if False then disable SSL verification
        when connecting to Galaxy instance (default is to keep
        SSL verification)

    """
    print "Fetching API key from %s" % galaxy_url
    email,password = handle_credentials(
        email,password,
        prompt="Please supply password for %s: " % galaxy_url)
    gi = get_galaxy_instance(galaxy_url,
                             email=email,password=password,
                             verify=verify)
    return users.get_user_api_key(gi,username=email)

def nebulizer(args=None):
    """
    Implements the 'nebulizer' command

    """
    if args is None:
        args = sys.argv[1:]

    p = base_parser(usage=\
                    "\n\t%prog list"
                    "\n\t%prog add ALIAS GALAXY_URL [API_KEY]"
                    "\n\t%prog update ALIAS"
                    "\n\t%prog remove ALIAS",
                    description="Admin commands for Galaxy instances")
    commands = ['list','add','update','remove']

    # Handle standard options
    if len(args) == 0:
        p.error("need to supply a command")
    elif len(args) == 1:
        if args[0] == '-h' or args[0] == '--help':
            p.print_usage()
        elif args[0] == '--version':
            p.print_version()
        if args[0] in ('-h','--help','--version'):
            sys.exit(0)

    # Identify major command
    command = args[0]
    args = args[1:]

    # Set up parser for specific commands
    if command not in commands:
        p.error("unrecognised command: '%s'" % command)
    elif command == 'list':
        p.set_usage("%prog list")
    elif command == 'add':
        p.set_usage("%prog add ALIAS GALAXY_URL [API_KEY]")
    elif command == 'update':
        p.set_usage("%prog update ALIAS")
        p.add_option('--new-url',action='store',dest='new_url',
                     default=None,
                     help="specify new URL for Galaxy instance")
        p.add_option('--new-api-key',action='store',dest='new_api_key',
                     default=None,
                     help="specify new API key for Galaxy instance")
        p.add_option('--fetch-api-key',action='store_true',
                     dest='fetch_api_key',
                     help="fetch new API key for Galaxy instance")
    elif command == 'remove':
        p.set_usage("%prog remove ALIAS")

    # Execute command
    options,args = p.parse_args(args)
    if command == 'list':
        instances = Credentials()
        for alias in instances.list_keys():
            galaxy_url,api_key = instances.fetch_key(alias)
            print "%s\t%s\t%s" % (alias,galaxy_url,api_key)
    elif command == 'add':
        if len(args) == 3:
            alias,galaxy_url,api_key = args[:3]
        elif len(args) == 2:
            # No API key supplied
            alias,galaxy_url = args[:2]
            api_key = None
        instances = Credentials()
        if alias in instances.list_keys():
            logging.error("'%s' already exists" % alias)
            sys.exit(1)
        if api_key is None:
            # Attempt to fetch new API key
            if options.username is None:
                p.error("Need to supply an API key, or a username (-u)")
            handle_ssl_warnings(verify=(not options.no_verify))
            handle_debug(debug=options.debug)
            api_key = fetch_api_key(galaxy_url,
                                    options.username,
                                    options.galaxy_password,
                                    verify=(not options.no_verify))
            if api_key is None:
                logging.error("Failed to get API key from %s" %
                              galaxy_url)
                sys.exit(1)
        else:
            p.error("Need to supply alias name, Galaxy URL and API key")
        # Store the entry
        instances.store_key(alias,galaxy_url,api_key)
    elif command == 'update':
        if len(args) == 1:
            alias = args[0]
        else:
            p.error("Need to supply alias name to be updated")
        instances = Credentials()
        if alias not in instances.list_keys():
            logging.error("'%s': not found" % alias)
            sys.exit(1)
        if options.fetch_api_key:
            # Attempt to fetch new API key
            handle_ssl_warnings(verify=(not options.no_verify))
            handle_debug(debug=options.debug)
            new_api_key = fetch_api_key(alias,
                                        options.username,
                                        options.galaxy_password,
                                        verify=(not options.no_verify))
            if new_api_key is None:
                logging.error("Failed to get new API key from %s" %
                              alias)
                if options.username is None:
                    logging.error("Invalid existing API key? Try "
                                  "specifying user name with -u")
                sys.exit(1)
        else:
            new_api_key = options.new_api_key
        instances.update_key(alias,
                             new_url=options.new_url,
                             new_api_key=new_api_key)
    elif command == 'remove':
        if len(args) == 1:
            alias = args[0]
        else:
            p.error("Need to supply alias name to be removed")
        instances = Credentials()
        instances.remove_key(alias)

def manage_users(args=None):
    """
    Implements the 'manage_users' utility

    """
    if args is None:
        args = sys.argv[1:]

    p = base_parser(usage=\
                    "\n\t%prog list   GALAXY_URL [options]"
                    "\n\t%prog create GALAXY_URL EMAIL [PUBLIC_NAME]"
                    "\n\t%prog create GALAXY_URL -t TEMPLATE START [END]"
                    "\n\t%prog create GALAXY_URL -b FILE [options]",
                    description="Manage and create users in a Galaxy "
                    "instance")
    commands = ['list','create']

    # Get compulsory arguments
    if len(args) == 1:
        if args[0] == '-h' or args[0] == '--help':
            p.print_usage()
        elif args[0] == '--version':
            p.print_version()
        sys.exit(0)
    if len(args) < 2:
        p.error("need to supply a command and a Galaxy URL/alias")
    command = args[0]
    galaxy_url = args[1]

    # Setup additional command line options
    if command not in commands:
        p.error("unrecognised command: '%s'" % command)
    elif command == 'list':
        p.set_usage("%prog list GALAXY_URL [options]")
        p.add_option('--name',action='store',dest='name',default=None,
                     help="specific emails/user name(s) to list")
        p.add_option('-l',action='store_true',
                     dest='long_listing_format',default=False,
                     help="use a long listing format (include ids, "
                     "disk usage and admin status)")
    elif command == 'create':
        p.set_usage("\n\t%prog create GALAXY_URL EMAIL [PUBLIC_NAME]"
                    "\n\t%prog create GALAXY_URL -t TEMPLATE START [END]"
                    "\n\t%prog create GALAXY_URL -b FILE [options]")
        p.add_option('-p','--password',action='store',dest='passwd',
                     default=None,
                     help="specify password for new user account "
                     "(otherwise program will prompt for password)")
        p.add_option('-c','--check',action='store_true',dest='check',
                     default=False,
                     help="check user details but don't try to create "
                     "the new account")
        p.add_option('-t','--template',action='store_true',
                     dest='template',default=False,
                     help="indicates that EMAIL is actually a "
                     "'template' email address which includes a '#' "
                     "symbol as a placeholder where an integer index "
                     "should be substituted to make multiple accounts "
                     "(e.g. 'student#@galaxy.ac.uk').")
        p.add_option('-b','--batch',action='store_true',dest='batch',
                     default=False,
                     help="create multiple users reading details from "
                     "TSV file (columns should be: "
                     "email,password[,public_name])")
        p.add_option('-m','--message',action='store',
                     dest='message_template',default=None,
                     help="populate and output Mako template "
                     "MESSAGE_TEMPLATE")
        
    # Process remaining arguments on command line
    if args[1] in ('-h','--help','--version'):
        args = args[1:]
    else:
        args = args[2:]
    options,args = p.parse_args(args)
    handle_debug(debug=options.debug)
    handle_suppress_warnings(suppress_warnings=options.suppress_warnings)
    handle_ssl_warnings(verify=(not options.no_verify))

    # Handle password if required
    email,password = handle_credentials(options.username,
                                        options.galaxy_password,
                                        prompt="Password for %s: " % galaxy_url)

    # Get a Galaxy instance
    gi = get_galaxy_instance(galaxy_url,api_key=options.api_key,
                             email=email,password=password,
                             verify=(not options.no_verify))
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        sys.exit(1)

    # Execute command
    if command == 'list':
        users.list_users(gi,name=options.name,long_listing_format=
                         options.long_listing_format)
    elif command == 'create':
        # Check message template is .mako file
        if options.message_template:
            if not os.path.isfile(options.message_template):
                logging.critical("Message template '%s' not found"
                                 % options.message_template)
                sys.exit(1)
            elif not options.message_template.endswith(".mako"):
                logging.critical("Message template '%s' is not a .mako file"
                                 % options.message_template)
                sys.exit(1)
        if options.template:
            # Get the template and range of indices
            template = args[0]
            start = int(args[1])
            try:
                end = int(args[2])
            except IndexError:
                end = start
            # Create users
            retval = users.create_users_from_template(gi,template,
                                                      start,end,options.passwd,
                                                      only_check=options.check)
        elif options.batch:
            # Get the file with the user data
            tsvfile = args[0]
            # Create users
            retval = users.create_batch_of_users(gi,tsvfile,
                                                 only_check=options.check,
                                                 mako_template=options.message_template)
        else:
            # Collect email and (optionally) public name
            email = args[0]
            try:
                name = args[1]
                if not users.check_username_format(name):
                    logging.critical("Invalid name: must contain only "
                                     "lower-case letters, numbers and "
                                     "'-'")
                    sys.exit(1)
            except IndexError:
                # No public name supplied, make from email address
                name = users.get_username_from_login(email)
            # Create user
            print "Email : %s" % email
            print "Name  : %s" % name
            retval = users.create_user(gi,email,name,options.passwd,
                                       only_check=options.check,
                                       mako_template=options.message_template)


def manage_libraries(args=None):
    """
    Implements the 'manage_libraries' utility

    """
    if args is None:
        args = sys.argv[1:]

    p = base_parser(usage=\
                    "\n\t%prog list GALAXY_URL [options]"
                    "\n\t%prog create_library GALAXY_URL [options] NAME"
                    "\n\t%prog create_folder GALAXY_URL [options] PATH"
                    "\n\t%prog add_datasets GALAXY_URL [options] DEST FILE...",
                    description="Manage and populate data libraries in a "
                    "Galaxy instance")
    
    commands = ['list','create_library','create_folder','add_datasets']

    # Get compulsory arguments
    if len(args) == 1:
        if args[0] == '-h' or args[0] == '--help':
            p.print_usage()
        elif args[0] == '--version':
            p.print_version()
        sys.exit(0)
    if len(args) < 2:
        p.error("need to supply a command and a Galaxy URL/alias")
    command = args[0]
    galaxy_url = args[1]

    # Setup additional command line options
    if command not in commands:
        p.error("unrecognised command: '%s'" % command)
    elif command == 'list':
        p.set_usage("%prog list GALAXY_URL [options]")
        p.add_option('-l',action='store_true',
                     dest='long_listing_format',default=False,
                     help="use a long listing format (include ids, "
                     "descriptions and file sizes and paths)")
    elif command == 'create_library':
        p.set_usage("%prog create_library GALAXY_URL [options] NAME")
        p.add_option('-d','--description',action='store',
                     dest='description',default=None,
                     help="optional description")
        p.add_option('-s','--synopsis',action='store',dest='synopsis',
                     default=None,help="optional synopsis")
    elif command == 'create_folder':
        p.set_usage("%prog create_folder GALAXY_URL [options] PATH")
        p.add_option('-d','--description',action='store',
                     dest='description',default=None,
                     help="optional description")
    elif command == 'add_datasets':
        p.set_usage("%prog add_datasets GALAXY_URL [options] DEST FILE...")
        p.add_option('--server',action='store_true',dest='from_server',
                     default=False,
                     help="upload files from Galaxy server file system "
                     "paths (default is to upload files from local "
                     "system)")
        p.add_option('--link',action='store_true',dest='link',
                     default=False,
                     help="create symlinks to files on server (only "
                     "valid if used with --server; default is to copy "
                     "files into Galaxy)")
        p.add_option('--dbkey',action='store',dest='dbkey',default='?',
                     help="dbkey to assign to files (default is '?')")
        p.add_option('--file_type',action='store',dest='file_type',
                     default='auto',
                     help="file type to assign to files (default is "
                     "'auto')")

    # Process remaining arguments on command line
    if args[1] in ('-h','--help','--version'):
        args = args[1:]
    else:
        args = args[2:]
    options,args = p.parse_args(args)
    handle_debug(debug=options.debug)
    handle_suppress_warnings(suppress_warnings=options.suppress_warnings)
    handle_ssl_warnings(verify=(not options.no_verify))

    # Handle password if required
    email,password = handle_credentials(options.username,
                                        options.galaxy_password,
                                        prompt="Password for %s: " % galaxy_url)

    # Get a Galaxy instance
    gi = get_galaxy_instance(galaxy_url,api_key=options.api_key,
                             email=email,password=password,
                             verify=(not options.no_verify))
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        sys.exit(1)

    # Execute command
    if command == 'list':
        if len(args) == 1:
            # List folders in data library
            libraries.list_library_contents(gi,args[0],long_listing_format=
                                            options.long_listing_format)
        else:
            # List data libraries
            libraries.list_data_libraries(gi)
    elif command == 'create_library':
        # Create a new data library
        if len(args) == 1:
            libraries.create_library(gi,args[0],
                                     description=options.description,
                                     synopsis=options.synopsis)
        else:
            p.error("Usage: create_library NAME")
    elif command == 'create_folder':
        # Create a new folder data library
        if len(args) == 1:
            libraries.create_folder(gi,args[0],
                                    description=options.description)
        else:
            p.error("Usage: create_folder PATH")
    elif command == 'add_datasets':
        # Add a dataset to a library
        if len(args) < 2:
            p.error("Usage: add_datasets DEST FILE [FILE...]")
        libraries.add_library_datasets(gi,args[0],args[1:],
                                       from_server=options.from_server,
                                       link_only=options.link,
                                       file_type=options.file_type,
                                       dbkey=options.dbkey)
 
def manage_tools(args=None):
    """
    Implements the 'manage_tools' utility

    """
    if args is None:
        args = sys.argv[1:]

    p = base_parser(usage=\
                    "\n\t%prog list GALAXY_URL [options]"
                    "\n\t%prog installed GALAXY_URL [options]"
                    "\n\t%prog tool_panel GALAXY_URL [options]"
                    "\n\t%prog install GALAXY_URL [options] SHED OWNER TOOL [REVISION]"
                    "\n\t%prog update GALAXY_URL [options] SHED OWNER TOOL",
                    description="Manage and install tools in a Galaxy "
                    "instance")
    
    commands = ['list','installed','tool_panel','install','update']

    # Get compulsory arguments
    if len(args) == 1:
        if args[0] == '-h' or args[0] == '--help':
            p.print_usage()
        elif args[0] == '--version':
            p.print_version()
        sys.exit(0)
    if len(args) < 2:
        p.error("need to supply a command and a Galaxy URL/alias")
    command = args[0]
    galaxy_url = args[1]

    # Setup additional command line options
    if command not in commands:
        p.error("unrecognised command: '%s'" % command)
    elif command == 'list':
        p.set_usage("%prog list GALAXY_URL [options]")
        p.add_option('--name',action='store',dest='name',default=None,
                     help="specific tool name(s) to list")
        p.add_option('--installed',action='store_true',
                     dest='installed_only',default=False,
                     help="only list tools installed from a toolshed")
    elif command == 'installed':
        p.set_usage("%prog installed GALAXY_URL [options]")
        p.add_option('--name',action='store',dest='name',default=None,
                     help="specific tool repository/ies to list")
        p.add_option('--toolshed',action='store',dest='toolshed',default=None,
                     help="only list repositories from TOOLSHED")
        p.add_option('--owner',action='store',dest='owner',default=None,
                     help="only list repositories owned by OWNER")
        p.add_option('--list-tools',action='store_true',dest='list_tools',
                     default=None,
                     help="list the associated tools for each repository")
        p.add_option('--updateable',action='store_true',dest='updateable',
                     default=None,
                     help="only show repositories with uninstalled updates "
                     "or upgrades")
    elif command == 'tool_panel':
        p.set_usage("%prog tool_panel GALAXY_URL [options]")
        p.add_option('--name',action='store',dest='name',default=None,
                     help="specific tool panel section(s) to list")
        p.add_option('--list-tools',action='store_true',dest='list_tools',
                     default=None,
                     help="list the associated tools for each section")
    elif command == 'install':
        p.set_usage("%prog install GALAXY_URL [options] SHED OWNER TOOL "
                    "[REVISION]")
        p.add_option('--tool-panel-section',action='store',
                     dest='tool_panel_section',default=None,
                     help="tool panel section name or id to install the "
                     "tool under")
    elif command == 'update':
        p.set_usage("%prog update GALAXY_URL [options] SHED OWNER TOOL")

    # Process remaining arguments on command line
    if args[1] in ('-h','--help','--version'):
        args = args[1:]
    else:
        args = args[2:]
    options,args = p.parse_args(args)
    handle_debug(debug=options.debug)
    handle_suppress_warnings(suppress_warnings=options.suppress_warnings)
    handle_ssl_warnings(verify=(not options.no_verify))

    # Handle password if required
    email,password = handle_credentials(options.username,
                                        options.galaxy_password,
                                        prompt="Password for %s: " % galaxy_url)

    # Get a Galaxy instance
    gi = get_galaxy_instance(galaxy_url,api_key=options.api_key,
                             email=email,password=password,
                             verify=(not options.no_verify))
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        sys.exit(1)

    # Execute command
    if command == 'list':
        tools.list_tools(gi,name=options.name,
                         installed_only=options.installed_only)
    elif command == 'installed':
        tools.list_installed_repositories(gi,name=options.name,
                                          toolshed=options.toolshed,
                                          owner=options.owner,
                                          list_tools=options.list_tools,
                                          only_updateable=options.updateable)
    elif command == 'tool_panel':
        tools.list_tool_panel(gi,name=options.name,
                              list_tools=options.list_tools)
    elif command == 'install':
        if len(args) < 3:
            p.error("Need to supply toolshed, owner, repo and optional "
                    "revision")
        toolshed,owner,repo = args[:3]
        if len(args) == 4:
            revision = args[3]
        else:
            revision = None
        status = tools.install_tool(
            gi,toolshed,repo,owner,revision=revision,
            tool_panel_section=options.tool_panel_section)
        sys.exit(status)
    elif command == 'update':
        if len(args) != 3:
            p.error("Need to supply toolshed, owner and repo")
        toolshed,owner,repo = args[:3]
        status = tools.update_tool(gi,toolshed,repo,owner)
        sys.exit(status)
