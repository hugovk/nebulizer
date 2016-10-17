#!/usr/bin/env python
#
# cli: functions for building command utilities
import sys
import os
import optparse
import getpass
import logging
import click
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

def fetch_new_api_key(galaxy_url,email,password=None,verify=True):
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

class Context(object):
    """
    Provide context for nebulizer command
    """
    def __init__(self):
        self.api_key = None
        self.username = None
        self.galaxy_password = None
        self.no_verify = False
        self.debug = False

    def galaxy_instance(self,alias):
        """
        Return Galaxy instance based on context

        Attempts to create a Bioblend based on the supplied
        arguments to the nebulizer command.
        """
        email,password = handle_credentials(
            self.username,
            self.galaxy_password,
            prompt="Password for %s: " % alias)
        gi = get_galaxy_instance(alias,api_key=self.api_key,
                                 email=email,password=password,
                                 verify=(not self.no_verify))
        return gi

pass_context = click.make_pass_decorator(Context,ensure=True)

@click.group()
@click.version_option(version=get_version())
@click.option('--api_key','-k',
              help="specify API key for Galaxy instance")
@click.option('--username','-u',
              help="specify username or email to log into Galaxy with")
@click.option('--galaxy_password','-P',
              help="supply password for Galaxy instance")
@click.option('--no-verify','-n',is_flag=True,
              help="don't verify HTTPS connections")
@click.option('--suppress-warnings','-q',is_flag=True,
              help="suppress warning messages")
@click.option('--debug',is_flag=True,
              help="turn on debugging output")
@pass_context
def nebulizer(context,api_key,username,galaxy_password,
              no_verify,suppress_warnings,debug):
    """
    Manage users, tools and data libraries in Galaxy instances
    via the API
    """
    context.api_key = api_key
    context.username = username
    context.galaxy_password = galaxy_password
    context.no_verify = no_verify
    context.debug = debug
    context.suppress_warnings = suppress_warnings
    handle_debug(debug=context.debug)
    handle_suppress_warnings(suppress_warnings=context.suppress_warnings)
    handle_ssl_warnings(verify=(not context.no_verify))

@nebulizer.command()
@pass_context
def list_keys(context):
    """
    List stored Galaxy API keys
    """
    instances = Credentials()
    for alias in instances.list_keys():
        galaxy_url,api_key = instances.fetch_key(alias)
        click.echo("%s\t%s\t%s" % (alias,galaxy_url,api_key))

@nebulizer.command()
@click.argument("alias")
@click.argument("galaxy_url")
@click.argument("api_key",required=False)
@pass_context
def add_key(context,alias,galaxy_url,api_key=None):
    """
    Store new Galaxy URL and API key

    ALIAS is the name that the instance will be stored
    against; GALAXY_URL is the URL for the instance;
    API_KEY is the corresponding API key.

    If API_KEY is not supplied then nebulizer will
    attempt to fetch one automatically.
    """
    instances = Credentials()
    if alias in instances.list_keys():
        logging.error("'%s' already exists" % alias)
        return 1
    if api_key is None:
        # No API key supplied as argument
        if context.api_key:
            api_key = context.api_key
        elif context.username:
            api_key = fetch_new_api_key(galaxy_url,
                                        context.username,
                                        context.galaxy_password,
                                        verify=(not context.no_verify))
            if api_key is None:
                logging.error("Failed to get API key from %s" %
                              galaxy_url)
                return 1
        else:
            logging.error("Need to supply an API key, or a username (-u)")
            return
    # Store the entry
    instances.store_key(alias,galaxy_url,api_key)

@nebulizer.command()
@click.option('--new-url',
              help="specify new URL for Galaxy instance")
@click.option('--new-api-key',
              help="specify new API key for Galaxy instance")
@click.option('--fetch-api-key',is_flag=True,
              help="fetch new API key for Galaxy instance")
@click.argument("alias")
@pass_context
def update_key(context,alias,new_url,new_api_key,fetch_api_key):
    """
    Update stored Galaxy API key
    """
    instances = Credentials()
    if alias not in instances.list_keys():
        logging.error("'%s': not found" % alias)
        return 1
    if new_url:
        galaxy_url = new_url
    else:
        galaxy_url = instances.fetch_key(alias)[0]
    click.echo("galaxy_url: %s" % galaxy_url)
    click.echo("username  : %s" % context.username)
    if fetch_api_key:
        # Attempt to fetch new API key
        try:
            new_api_key = fetch_new_api_key(galaxy_url,
                                            context.username,
                                            context.galaxy_password,
                                            verify=(not context.no_verify))
        except AttributeError:
            new_api_key = None
        if new_api_key is None:
            logging.error("Failed to get new API key from %s" %
                          alias)
            if context.username is None:
                logging.error("Invalid existing API key? Try "
                              "specifying user name with -u")
            return 1
    instances.update_key(alias,
                         new_url=new_url,
                         new_api_key=new_api_key)

@nebulizer.command()
@click.argument("alias")
@pass_context
def remove_key(context,alias):
    """
    Remove stored Galaxy API key
    """
    instances = Credentials()
    instances.remove_key(alias)

@nebulizer.command()
@click.option("--name",
              help="specific emails/user name(s) to list")
@click.option("--long","-l","long_listing",is_flag=True,
              help="use a long listing format (include ids,"
              " disk usage and admin status)")
@click.argument("galaxy")
@pass_context
def list_users(context,galaxy,name,long_listing):
    """
    List users in Galaxy instance
    """
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # List users
    users.list_users(gi,name=name,long_listing_format=long_listing)

@nebulizer.command()
@click.option('--password','-p',
              help="specify password for new user account "
              "(otherwise program will prompt for password)")
@click.option('--check','-c','only_check',is_flag=True,
              help="check user details but don't try to create the "
              "new account")
@click.option('--message','-m','message_template',
              type=click.Path(exists=True),
              help="Mako template to populate and output")
@click.argument("galaxy")
@click.argument("email")
@click.argument("public_name",required=False)
@pass_context
def create_user(context,galaxy,email,public_name,password,only_check,
                message_template):
    """
    Create new Galaxy user
    """
    # Check message template is a .mako file
    if message_template:
        if not message_template.endswith(".mako"):
            logging.critical("Message template '%s' is not a .mako file"
                             % message_template)
            return 1
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # Sort out email and public name
    if public_name:
        if not users.check_username_format(public_name):
            logging.critical("Invalid public name: must contain only "
                             "lower-case letters, numbers and '-'")
            return 1
    else:
        # No public name supplied, make from email address
        name = users.get_username_from_login(email)
    # Create user
    print "Email : %s" % email
    print "Name  : %s" % name
    return users.create_user(gi,email,name,password,
                             only_check=only_check,
                             mako_template=message_template)

@nebulizer.command()
@click.option('--password','-p',
              help="specify password for new user accounts "
              "(otherwise program will prompt for password). "
              "All accounts will be created with the same "
              "password")
@click.option('--check','-c','only_check',is_flag=True,
              help="check user details but don't try to create the "
              "new account")
@click.argument("galaxy")
@click.argument("template")
@click.argument("start")
@click.argument("end",required=False)
@pass_context
def create_users_from_template(context,galaxy,template,start,end,
                               password,only_check):
    """
    Create multiple Galaxy users from a template

    TEMPLATE is a 'template' email address which includes a
    '#' symbol as a placeholder where an integer index
    should be substituted to make multiple accounts (e.g.
    'student#@galaxy.ac.uk')
    """
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # Sort out start and end indices
    if end is not None:
        end = start
        start = 1
    # Create users
    return users.create_users_from_template(gi,template,
                                            start,end,password,
                                            only_check=only_check)

@nebulizer.command()
@click.option('--password','-p',
              help="specify password for new user accounts "
              "(otherwise program will prompt for password). "
              "All accounts will be created with the same "
              "password")
@click.option('--check','-c','only_check',is_flag=True,
              help="check user details but don't try to create the "
              "new account")
@click.option('--message','-m','message_template',
              type=click.Path(exists=True),
              help="Mako template to populate and output")
@click.argument("galaxy")
@click.argument("file")
@pass_context
def create_users_from_file(context,galaxy,tsvfile,password,only_check):
    """
    Create multiple Galaxy users from a file

    TSVFILE is a tab-delimited file with details of a new user
    on each line; the columns should be 'email','password', and
    optionally 'public_name'.
    """
    # Check message template is a .mako file
    if message_template:
        if not message_template.endswith(".mako"):
            logging.critical("Message template '%s' is not a .mako file"
                             % message_template)
            return 1
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # Sort out start and end indices
    if end is not None:
        end = start
        start = 1
    # Create users
    return users.create_batch_of_users(gi,tsvfile,
                                       only_check=only_check,
                                       mako_template=message_template)

@nebulizer.command()
@click.option('--name',
              help="specific tool name(s) to list")
@click.option('--installed','installed_only',is_flag=True,
              help="only list tools installed from a toolshed")
@click.argument("galaxy")
@pass_context
def list_tools(context,galaxy,name,installed_only):
    """
    List tools in Galaxy instance
    """
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # List tools
    tools.list_tools(gi,name=name,installed_only=installed_only)

@nebulizer.command()
@click.option('--name',
              help="specific tool repository name(s) to list")
@click.option('--toolshed',
              help="only list repositories from specified toolshed")
@click.option('--owner',
              help="only list repositories from specified owner")
@click.option('--list-tools',is_flag=True,
              help="list the tools associated with each repository "
              "revision")
@click.option('--updateable',is_flag=True,
              help="only show repositories with uninstalled updates "
              "or upgrades")
@click.argument("galaxy")
@pass_context
def list_installed_tools(context,galaxy,name,toolshed,owner,list_tools,
                         updateable):
    """
    List installed tool repositories
    """
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # List repositories
    tools.list_installed_repositories(gi,name=name,
                                      toolshed=toolshed,
                                      owner=owner,
                                      list_tools=list_tools,
                                      only_updateable=updateable)

@nebulizer.command()
@click.option('--name',
              help="specific tool panel section(s) to list")
@click.option('--list-tools',is_flag=True,
              help="also list the associated tools for each "
              "section")
@click.argument("galaxy")
@pass_context
def list_tool_panel(context,alias,name,list_tools):
    """
    List tool panel contents
    """
    
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # List tool panel contents
    tools.list_tool_panel(gi,name=name,
                          list_tools=list_tools)

@nebulizer.command()
@click.option('--tool-panel-section',
              help="tool panel section name or id to install "
              "the tool under")
@click.argument("galaxy")
@click.argument("toolshed")
@click.argument("owner")
@click.argument("repository")
@click.argument("revision",required=False)
@pass_context
def install_tool(context,galaxy,toolshed,owner,repository,
                 revision,tool_panel_section):
    """
    Install tool from toolshed
    """
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # Install tool
    return tools.install_tool(
        gi,toolshed,repository,owner,revision=revision,
        tool_panel_section=tool_panel_section)

@nebulizer.command()
@click.argument("galaxy")
@click.argument("toolshed")
@click.argument("owner")
@click.argument("repository")
@pass_context
def update_tool(context,galaxy,toolshed,owner,repository):
    """
    Update tool installed from toolshed
    """
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # Install tool
    return tools.update_tool(gi,toolshed,repository,owner)

@nebulizer.command()
@click.option('-l','long_listing',is_flag=True,
              help="use a long listing format (include ids, "
              "descriptions and file sizes and paths)")
@click.argument("galaxy")
@click.argument("path",required=False)
@pass_context
def list_libraries(context,galaxy,path,long_listing):
    """
    List data libraries and contents
    """
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # List folders in data library
    if path:
        libraries.list_library_contents(gi,path,
                                        long_listing_format=
                                        long_listing)
    else:
        libraries.list_data_libraries(gi)

@nebulizer.command()
@click.option('-d','--description',
              help="description of the new library")
@click.option('-s','--synopsis',
              help="synopsis text for the new library")
@click.argument("galaxy")
@click.argument("name")
@pass_context
def create_library(context,galaxy,name,description,synopsis):
    """
    Create new data library
    """
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # Create new data library
    libraries.create_library(gi,name,
                             description=description,
                             synopsis=synopsis)

@nebulizer.command()
@click.option('-d','--description',
              help="description of the new folder")
@click.argument("galaxy")
@click.argument("path")
@pass_context
def create_library_folder(context,galaxy,path,description):
    """
    Create new folder in a data library
    """
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # Create new folder
    libraries.create_folder(gi,path,description=description)

@nebulizer.command()
@click.option('--file-type',default='auto',
              help="Galaxy data type to assign the files to "
              "(default is 'auto'). Must be a valid Galaxy "
              "data type. If not 'auto' then all files will "
              "be assigned the same type.")
@click.option('--dbkey',default='?',
              help="dbkey to assign to files (default is '?')")
@click.option('--server','from_server',is_flag=True,
              help="upload files from the Galaxy server file "
              "system (default is to upload files from local "
              "system)")
@click.option('--link',is_flag=True,
              help="create symlinks to files on server (only "
              "valid if used with --server; default is to copy "
              "files into Galaxy)")
@click.argument("galaxy")
@click.argument("dest")
@click.argument("file","files",nargs=-1)
@pass_context
def add_library_datasets(context,galaxy,dest):
    """
    Add datasets to a data library
    """
    # Get a Galaxy instance
    gi = context.galaxy_instance(galaxy)
    if gi is None:
        logging.critical("Failed to connect to Galaxy instance")
        return 1
    # Add the datasets
    libraries.add_library_datasets(gi,dest,files,
                                   from_server=options.from_server,
                                   link_only=options.link,
                                   file_type=options.file_type,
                                   dbkey=options.dbkey)
    
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
